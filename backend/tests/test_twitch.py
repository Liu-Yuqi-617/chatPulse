import asyncio
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

from app.config import Settings
from app.state import StateStore
from app.twitch import TwitchService
import pytest


def make_service() -> TwitchService:
    settings = Settings(
        twitch_client_id="test-client",
        twitch_client_secret="test-secret",
        twitch_redirect_uri="http://localhost:8000/api/auth/twitch/callback",
    )
    return TwitchService(settings, StateStore())


def test_login_url_uses_authorization_code_flow_and_chat_scope() -> None:
    service = make_service()

    url = urlparse(service.login_url())
    params = parse_qs(url.query)

    assert url.netloc == "id.twitch.tv"
    assert params["response_type"] == ["code"]
    assert params["scope"] == ["user:read:chat"]
    assert params["redirect_uri"] == ["http://localhost:8000/api/auth/twitch/callback"]
    assert params["state"][0]


def test_eventsub_notification_adds_real_chat_message() -> None:
    service = make_service()
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    service._ingest_notification(
        {
            "metadata": {"message_id": "event-1", "message_timestamp": timestamp},
            "payload": {
                "event": {
                    "message_id": "chat-1",
                    "broadcaster_user_id": "channel-1",
                    "chatter_user_id": "viewer-1",
                    "chatter_user_name": "ViewerOne",
                    "message": {"text": "When is the next stream?"},
                }
            },
        }
    )

    state = service.store.snapshot()
    assert state.messages[0].id == "chat-1"
    assert state.messages[0].display_name == "ViewerOne"
    assert state.questions[0].representative_question == "When is the next stream?"


def test_cannot_track_before_twitch_is_connected() -> None:
    service = make_service()

    with pytest.raises(RuntimeError, match="Connect Twitch first"):
        asyncio.run(service.track_live_stream())
