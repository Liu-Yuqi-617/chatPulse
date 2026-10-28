from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import uuid4

from app.models import (
    ChatMessage,
    DashboardState,
    QuestionGroup,
    QuestionStatus,
    Spotlight,
    Topic,
)


SCENARIOS: dict[str, list[tuple[str, str]]] = {
    "mixed": [
        ("PixelMochi", "Are you playing Minecraft tomorrow?"),
        ("NightOwl", "When is the next Minecraft stream?"),
        ("LunaLive", "Can you try the new Minecraft update?"),
        ("SoundCheck", "What microphone are you using?"),
        ("CozyBean", "Your mic sounds really good!"),
    ],
    "questions": [
        ("Jamie", "When is your next stream?"),
        ("River", "Are you streaming tomorrow?"),
        ("Nova", "What is your schedule this week?"),
        ("Jamie", "Which game will you play next?"),
    ],
    "quiet": [
        ("FirstTimer", "Hello! First time watching."),
        ("CozyBean", "Hope everyone is having a great day."),
    ],
}


class StateStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._messages: list[ChatMessage] = []
        self._topics: list[Topic] = []
        self._questions: list[QuestionGroup] = []
        self._spotlight = Spotlight(updated_at=datetime.now(UTC))
        self._updated_at = datetime.now(UTC)

    def snapshot(self) -> DashboardState:
        with self._lock:
            return DashboardState(
                messages=self._messages,
                topics=self._topics,
                questions=self._questions,
                spotlight=self._spotlight,
                updated_at=self._updated_at,
            )

    def ingest_message(self, message: ChatMessage) -> DashboardState:
        """Add a real Twitch message while keeping the live state bounded."""
        now = datetime.now(UTC)
        with self._lock:
            if any(item.id == message.id for item in self._messages):
                return self.snapshot_unlocked()

            self._messages.append(message)
            self._messages = self._messages[-500:]

            # Until the LLM pipeline is enabled, expose real questions directly so
            # the streamer can already use the queue and spotlight end to end.
            if "?" in message.text or "？" in message.text:
                question = QuestionGroup(
                    id=f"question-{message.id}",
                    representative_question=message.text,
                    message_ids=[message.id],
                    unique_viewer_count=1,
                    priority_score=1.0,
                    last_seen_at=message.timestamp,
                )
                self._questions.insert(0, question)
                self._questions = self._questions[:100]

            self._topics = [
                Topic(
                    id="topic-live-chat",
                    title="Live chat activity",
                    summary="Messages received directly from the connected Twitch channel.",
                    message_ids=[item.id for item in self._messages[-30:]],
                    message_count=min(len(self._messages), 30),
                    updated_at=now,
                )
            ]
            self._updated_at = now
            return self.snapshot_unlocked()

    def apply_analysis(
        self, topics: list[Topic], questions: list[QuestionGroup]
    ) -> DashboardState:
        """Atomically replace AI results while preserving streamer workflow state."""
        now = datetime.now(UTC)
        with self._lock:
            previous = {item.id: item for item in self._questions}
            for question in questions:
                old = previous.get(question.id)
                if old is not None:
                    question.status = old.status

            pinned = next(
                (item for item in questions if item.status == QuestionStatus.PINNED),
                None,
            )
            self._topics = topics
            self._questions = questions
            if pinned is not None:
                self._spotlight = Spotlight(
                    question_id=pinned.id,
                    question_text=pinned.representative_question,
                    viewer_count=pinned.unique_viewer_count,
                    updated_at=now,
                )
            elif self._spotlight.question_id is not None:
                self._spotlight = Spotlight(updated_at=now)
            self._updated_at = now
            return self.snapshot_unlocked()

    def simulate(self, scenario: str) -> DashboardState:
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}")

        now = datetime.now(UTC)
        messages = [
            ChatMessage(
                id=f"msg-{uuid4().hex[:8]}",
                channel_id="demo-channel",
                user_id=f"viewer-{index}",
                display_name=display_name,
                text=text,
                timestamp=now - timedelta(seconds=(len(SCENARIOS[scenario]) - index) * 4),
                received_at=now,
            )
            for index, (display_name, text) in enumerate(SCENARIOS[scenario], start=1)
        ]

        topics, questions = self._analyze_demo(scenario, messages, now)
        with self._lock:
            self._messages = messages
            self._topics = topics
            self._questions = questions
            self._spotlight = Spotlight(updated_at=now)
            self._updated_at = now
            return self.snapshot_unlocked()

    def update_question(self, question_id: str, status: QuestionStatus) -> DashboardState:
        now = datetime.now(UTC)
        with self._lock:
            question = next((item for item in self._questions if item.id == question_id), None)
            if question is None:
                raise KeyError(question_id)

            if status == QuestionStatus.PINNED:
                for item in self._questions:
                    if item.status == QuestionStatus.PINNED:
                        item.status = QuestionStatus.NEW
                self._spotlight = Spotlight(
                    question_id=question.id,
                    question_text=question.representative_question,
                    viewer_count=question.unique_viewer_count,
                    updated_at=now,
                )
            elif self._spotlight.question_id == question.id:
                self._spotlight = Spotlight(updated_at=now)

            question.status = status
            self._updated_at = now
            return self.snapshot_unlocked()

    def clear_spotlight(self) -> DashboardState:
        now = datetime.now(UTC)
        with self._lock:
            for question in self._questions:
                if question.status == QuestionStatus.PINNED:
                    question.status = QuestionStatus.NEW
            self._spotlight = Spotlight(updated_at=now)
            self._updated_at = now
            return self.snapshot_unlocked()

    def snapshot_unlocked(self) -> DashboardState:
        return DashboardState(
            messages=self._messages,
            topics=self._topics,
            questions=self._questions,
            spotlight=self._spotlight,
            updated_at=self._updated_at,
        )

    @staticmethod
    def _analyze_demo(
        scenario: str, messages: list[ChatMessage], now: datetime
    ) -> tuple[list[Topic], list[QuestionGroup]]:
        if scenario == "mixed":
            topics = [
                Topic(
                    id="topic-minecraft",
                    title="Minecraft plans",
                    summary="Viewers want to know about the next Minecraft stream and update.",
                    message_ids=[item.id for item in messages[:3]],
                    message_count=3,
                    updated_at=now,
                ),
                Topic(
                    id="topic-audio",
                    title="Streaming setup",
                    summary="The audience is discussing the streamer's microphone quality.",
                    message_ids=[item.id for item in messages[3:]],
                    message_count=2,
                    updated_at=now,
                ),
            ]
            questions = [
                QuestionGroup(
                    id="question-minecraft",
                    representative_question="When is the next Minecraft stream?",
                    message_ids=[item.id for item in messages[:3]],
                    unique_viewer_count=3,
                    priority_score=0.94,
                    last_seen_at=now,
                ),
                QuestionGroup(
                    id="question-microphone",
                    representative_question="What microphone are you using?",
                    message_ids=[messages[3].id],
                    unique_viewer_count=1,
                    priority_score=0.58,
                    last_seen_at=now,
                ),
            ]
            return topics, questions

        if scenario == "questions":
            return (
                [
                    Topic(
                        id="topic-schedule",
                        title="Upcoming streams",
                        summary="Viewers are asking about the upcoming schedule and games.",
                        message_ids=[item.id for item in messages],
                        message_count=len(messages),
                        updated_at=now,
                    )
                ],
                [
                    QuestionGroup(
                        id="question-schedule",
                        representative_question="When is your next livestream?",
                        message_ids=[item.id for item in messages[:3]],
                        unique_viewer_count=3,
                        priority_score=0.96,
                        last_seen_at=now,
                    ),
                    QuestionGroup(
                        id="question-next-game",
                        representative_question="Which game will you play next?",
                        message_ids=[messages[3].id],
                        unique_viewer_count=1,
                        priority_score=0.51,
                        last_seen_at=now,
                    ),
                ],
            )

        return (
            [
                Topic(
                    id="topic-community",
                    title="Community check-in",
                    summary="A quiet, friendly moment with new and returning viewers.",
                    message_ids=[item.id for item in messages],
                    message_count=len(messages),
                    updated_at=now,
                )
            ],
            [],
        )


store = StateStore()

