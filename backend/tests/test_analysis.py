from datetime import UTC, datetime

from app.analysis import AnalyzedTopic, ChatAnalysis, AnalysisService
from app.models import ChatMessage


def message(message_id: str, user_id: str, text: str) -> ChatMessage:
    now = datetime.now(UTC)
    return ChatMessage(
        id=message_id,
        channel_id="channel",
        user_id=user_id,
        display_name=user_id,
        text=text,
        timestamp=now,
        received_at=now,
    )


def test_analysis_keeps_only_grounded_valid_questions_and_topics() -> None:
    messages = [
        message("m1", "u1", "When is the next stream?"),
        message("m2", "u2", "Great stream!"),
    ]
    result = ChatAnalysis(
        valid_question_ids=["m1", "missing"],
        topics=[
            AnalyzedTopic(
                title="Schedule",
                summary="A viewer asks about the next stream.",
                message_ids=["m1", "missing"],
            )
        ],
    )

    topics, questions = AnalysisService._build_models(result, messages)

    assert topics[0].message_ids == ["m1"]
    assert questions[0].representative_question == "When is the next stream?"
    assert questions[0].message_ids == ["m1"]


def test_analysis_drops_ungrounded_results() -> None:
    result = ChatAnalysis(
        valid_question_ids=["unknown"],
        topics=[AnalyzedTopic(title="Fake", summary="Fake", message_ids=["unknown"])],
    )

    topics, questions = AnalysisService._build_models(
        result, [message("m1", "u1", "Hello")]
    )

    assert topics == []
    assert questions == []
