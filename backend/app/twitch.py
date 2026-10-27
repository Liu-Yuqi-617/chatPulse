import asyncio
import json
import secrets
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from websockets.asyncio.client import connect

from app.config import Settings
from app.models import ChatMessage
from app.state import StateStore


TWITCH_AUTHORIZE_URL = "https://id.twitch.tv/oauth2/authorize"
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
TWITCH_EVENTSUB_URL = "wss://eventsub.wss.twitch.tv/ws"
TWITCH_SUBSCRIPTIONS_URL = "https://api.twitch.tv/helix/eventsub/subscriptions"
TWITCH_STREAMS_URL = "https://api.twitch.tv/helix/streams"


@dataclass
class TwitchCredentials:
    access_token: str
    refresh_token: str
    user_id: str
    login: str
    display_name: str


class TwitchService:
    def __init__(self, settings: Settings, store: StateStore) -> None:
        self.settings = settings
        self.store = store
        self._oauth_states: set[str] = set()
        self._credentials: TwitchCredentials | None = None
        self._eventsub_task: asyncio.Task[None] | None = None
        self._stream_task: asyncio.Task[None] | None = None
        self._stream: dict[str, Any] | None = None
        self._tracking = False
        self._status = "authentication_required"
        self._error: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.settings.twitch_client_id and self.settings.twitch_client_secret)

    def login_url(self) -> str:
        if not self.configured:
            raise RuntimeError("Twitch client ID and secret are not configured")
        state = secrets.token_urlsafe(32)
        self._oauth_states.add(state)
        params = {
            "client_id": self.settings.twitch_client_id,
            "redirect_uri": self.settings.twitch_redirect_uri,
            "response_type": "code",
            "scope": self.settings.twitch_scopes,
            "state": state,
        }
        return f"{TWITCH_AUTHORIZE_URL}?{urlencode(params)}"

    async def authorize(self, code: str, state: str) -> None:
        if state not in self._oauth_states:
            raise ValueError("Invalid or expired OAuth state")
        self._oauth_states.remove(state)

        async with httpx.AsyncClient(timeout=15) as client:
            token_response = await client.post(
                TWITCH_TOKEN_URL,
                data={
                    "client_id": self.settings.twitch_client_id,
                    "client_secret": self.settings.twitch_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.settings.twitch_redirect_uri,
                },
            )
            token_response.raise_for_status()
            tokens = token_response.json()
            access_token = tokens["access_token"]

            validate_response = await client.get(
                TWITCH_VALIDATE_URL,
                headers={"Authorization": f"OAuth {access_token}"},
            )
            validate_response.raise_for_status()
            identity = validate_response.json()

            user_response = await client.get(
                "https://api.twitch.tv/helix/users",
                headers=self._headers(access_token),
            )
            user_response.raise_for_status()
            users = user_response.json().get("data", [])
            display_name = users[0].get("display_name", identity["login"]) if users else identity["login"]

        self._credentials = TwitchCredentials(
            access_token=access_token,
            refresh_token=tokens.get("refresh_token", ""),
            user_id=identity["user_id"],
            login=identity["login"],
            display_name=display_name,
        )
        self._status = "ready"
        self._start_stream_monitor()

    def status(self) -> dict[str, Any]:
        credentials = self._credentials
        return {
            "configured": self.configured,
            "status": self._status,
            "channel_id": credentials.user_id if credentials else None,
            "channel_login": credentials.login if credentials else None,
            "channel_name": credentials.display_name if credentials else None,
            "stream": self._stream,
            "tracking": self._tracking,
            "error": self._error,
        }

    async def track_live_stream(self) -> dict[str, Any]:
        if not self._credentials:
            raise RuntimeError("Connect Twitch first")
        await self._refresh_stream()
        if not self._stream:
            raise RuntimeError("This Twitch channel is not live")
        if not self._tracking:
            self._tracking = True
            self._start_eventsub()
        return self.status()

    async def disconnect(self) -> None:
        task = self._eventsub_task
        stream_task = self._stream_task
        self._eventsub_task = None
        self._stream_task = None
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if stream_task:
            stream_task.cancel()
            with suppress(asyncio.CancelledError):
                await stream_task
        self._credentials = None
        self._stream = None
        self._tracking = False
        self._status = "authentication_required"
        self._error = None

    def _start_eventsub(self) -> None:
        if self._eventsub_task:
            self._eventsub_task.cancel()
        self._status = "connecting"
        self._error = None
        self._eventsub_task = asyncio.create_task(self._eventsub_loop())

    def _start_stream_monitor(self) -> None:
        if self._stream_task:
            self._stream_task.cancel()
        self._stream_task = asyncio.create_task(self._stream_monitor_loop())

    async def _stream_monitor_loop(self) -> None:
        while self._credentials:
            try:
                await self._refresh_stream()
            except asyncio.CancelledError:
                raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    await self._refresh_access_token()
            except httpx.HTTPError:
                pass
            await asyncio.sleep(15)

    async def _refresh_stream(self) -> None:
        credentials = self._credentials
        if not credentials:
            self._stream = None
            return
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                TWITCH_STREAMS_URL,
                params={"user_id": credentials.user_id},
                headers=self._headers(credentials.access_token),
            )
            response.raise_for_status()
            streams = response.json().get("data", [])
        if not streams:
            self._stream = None
            return
        stream = streams[0]
        self._stream = {
            "id": stream["id"],
            "title": stream.get("title") or "Untitled stream",
            "game_name": stream.get("game_name") or "No category",
            "viewer_count": stream.get("viewer_count", 0),
            "started_at": stream.get("started_at"),
        }

    async def _eventsub_loop(self) -> None:
        delay = 1
        websocket_url = TWITCH_EVENTSUB_URL
        should_subscribe = True
        while self._credentials:
            try:
                async with connect(websocket_url, ping_interval=None) as websocket:
                    welcome = json.loads(await asyncio.wait_for(websocket.recv(), timeout=15))
                    session = welcome.get("payload", {}).get("session", {})
                    if welcome.get("metadata", {}).get("message_type") != "session_welcome":
                        raise RuntimeError("Twitch did not send an EventSub welcome message")

                    if should_subscribe:
                        await self._subscribe(session["id"])
                    self._status = "connected"
                    self._error = None
                    delay = 1

                    async for raw_message in websocket:
                        payload = json.loads(raw_message)
                        message_type = payload.get("metadata", {}).get("message_type")
                        if message_type == "notification":
                            self._ingest_notification(payload)
                        elif message_type == "session_reconnect":
                            websocket_url = payload["payload"]["session"]["reconnect_url"]
                            should_subscribe = False
                            self._status = "reconnecting"
                            break
                        elif message_type == "revocation":
                            reason = payload.get("payload", {}).get("subscription", {}).get("status")
                            raise RuntimeError(f"EventSub subscription revoked: {reason}")
            except asyncio.CancelledError:
                raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401 and await self._refresh_access_token():
                    self._error = None
                else:
                    self._error = f"Twitch API error ({exc.response.status_code})"
                self._status = "reconnecting"
                should_subscribe = True
                websocket_url = TWITCH_EVENTSUB_URL
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
            except Exception as exc:
                self._status = "reconnecting"
                self._error = str(exc)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
                websocket_url = TWITCH_EVENTSUB_URL
                should_subscribe = True

    async def _subscribe(self, session_id: str) -> None:
        credentials = self._credentials
        if not credentials:
            raise RuntimeError("Twitch is not authorized")
        body = {
            "type": "channel.chat.message",
            "version": "1",
            "condition": {
                "broadcaster_user_id": credentials.user_id,
                "user_id": credentials.user_id,
            },
            "transport": {"method": "websocket", "session_id": session_id},
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                TWITCH_SUBSCRIPTIONS_URL,
                headers=self._headers(credentials.access_token),
                json=body,
            )
            response.raise_for_status()

    async def _refresh_access_token(self) -> bool:
        credentials = self._credentials
        if not credentials or not credentials.refresh_token:
            self._status = "authentication_required"
            return False
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    TWITCH_TOKEN_URL,
                    data={
                        "client_id": self.settings.twitch_client_id,
                        "client_secret": self.settings.twitch_client_secret,
                        "grant_type": "refresh_token",
                        "refresh_token": credentials.refresh_token,
                    },
                )
                response.raise_for_status()
                tokens = response.json()
            credentials.access_token = tokens["access_token"]
            credentials.refresh_token = tokens.get("refresh_token", credentials.refresh_token)
            return True
        except (httpx.HTTPError, KeyError):
            self._status = "authentication_required"
            return False

    def _ingest_notification(self, payload: dict[str, Any]) -> None:
        event = payload.get("payload", {}).get("event", {})
        text = event.get("message", {}).get("text", "").strip()
        if not text:
            return
        timestamp = payload.get("metadata", {}).get("message_timestamp")
        sent_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if timestamp else datetime.now(UTC)
        message = ChatMessage(
            id=event.get("message_id") or payload["metadata"]["message_id"],
            channel_id=event["broadcaster_user_id"],
            user_id=event["chatter_user_id"],
            display_name=event["chatter_user_name"],
            text=text,
            timestamp=sent_at,
            received_at=datetime.now(UTC),
        )
        self.store.ingest_message(message)

    def _headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Client-Id": self.settings.twitch_client_id,
        }
