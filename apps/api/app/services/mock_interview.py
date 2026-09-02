import hashlib
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mock_interview import (
    MockInterviewSession,
    MockInterviewTurn,
    MockInterviewTurnEvaluation,
    MockReadinessReport,
)
from app.models.speech import SpeechAttempt, SpeechFeedback, SpeechTranscript
from app.models.user import User
from app.schemas.mock_interview import (
    MockBlueprintView,
    MockModeView,
    MockReadinessReportView,
    MockSessionCreateIn,
    MockSessionView,
    MockTurnEvaluationView,
    MockTurnView,
)
from app.services.learning import ensure_starter_learning, get_active_enrollment
from app.services.speech import attempt_view, require_consent

BLUEPRINT_PATH = (
    Path(__file__).resolve().parents[4] / "content" / "mock-interview-blueprint.v1.json"
)
STRUCTURE_MARKERS = (
    "zuerst",
    "dann",
    "danach",
    "anschließend",
    "deshalb",
    "dadurch",
    "weil",
    "am ende",
    "situation",
    "aufgabe",
    "ergebnis",
    "ziel",
)
TECHNICAL_TERMS = (
    "api",
    "backend",
    "frontend",
    "datenbank",
    "docker",
    "cloud",
    "python",
    "react",
    "service",
    "test",
    "monitor",
    "architektur",
    "system",
    "deployment",
)
FILLERS = ("äh", "ähm", "hm", "irgendwie", "halt")


def _canonical_checksum(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_blueprint() -> dict:
    payload = json.loads(BLUEPRINT_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise RuntimeError("Unsupported mock interview blueprint schema")
    question_list = payload.get("questions")
    modes = payload.get("modes")
    if not isinstance(question_list, list) or not isinstance(modes, dict):
        raise RuntimeError("Mock interview blueprint is malformed")
    questions = {str(item["key"]): item for item in question_list}
    if len(questions) != len(question_list):
        raise RuntimeError("Mock interview blueprint contains duplicate question keys")
    for mode_name, config in modes.items():
        keys = config.get("question_keys", [])
        if not keys or any(key not in questions for key in keys):
            raise RuntimeError(f"Mock mode {mode_name} references an invalid question")
    return payload


def blueprint_view() -> MockBlueprintView:
    blueprint = load_blueprint()
    return MockBlueprintView(
        key=blueprint["key"],
        version=int(blueprint["version"]),
        title=blueprint["title"],
        target_cefr=blueprint["target_cefr"],
        checksum=_canonical_checksum(blueprint),
        modes=[
            MockModeView(
                mode=mode,
                turn_count=len(config["question_keys"]),
                prep_seconds=int(config["prep_seconds"]),
                support=str(config["support"]),
            )
            for mode, config in blueprint["modes"].items()
        ],
    )


def _freeze_question(question: dict) -> dict:
    frozen = {
        "key": str(question["key"]),
        "category": str(question["category"]),
        "question": str(question["question"]),
        "intent": str(question.get("intent", "")),
        "hints": [str(item) for item in question.get("hints", [])],
        "target_duration_seconds": int(question.get("target_duration_seconds", 60)),
        "required_signals": [
            [str(value) for value in group]
            for group in question.get("required_signals", [])
        ],
    }
    if question.get("technical_terms"):
        frozen["technical_terms"] = [str(item) for item in question["technical_terms"]]
    if question.get("follow_up"):
        frozen["follow_up"] = _freeze_question(question["follow_up"])
    return frozen


async def create_session(
    db: AsyncSession,
    user: User,
    payload: MockSessionCreateIn,
) -> MockInterviewSession:
    blueprint = load_blueprint()
    mode_config = blueprint["modes"].get(payload.mode)
    if mode_config is None:
        raise ValueError("Unsupported mock interview mode")
    questions = {item["key"]: item for item in blueprint["questions"]}
    frozen_questions = [
        _freeze_question(questions[key]) for key in mode_config["question_keys"]
    ]
    default_seed = hashlib.sha256(f"{user.id}:{payload.mode}".encode()).hexdigest()[:16]
    seed = payload.seed or default_seed
    plan = {
        "schema_version": 1,
        "mode": payload.mode,
        "purpose": payload.purpose,
        "prep_seconds": int(mode_config["prep_seconds"]),
        "support": str(mode_config["support"]),
        "questions": frozen_questions,
    }
    now = datetime.now(UTC)
    interview = MockInterviewSession(
        user_id=user.id,
        blueprint_key=str(blueprint["key"]),
        blueprint_version=int(blueprint["version"]),
        blueprint_checksum=_canonical_checksum(blueprint),
        mode=payload.mode,
        purpose=payload.purpose,
        seed=seed,
        plan=plan,
        status="active",
        current_turn_key="01",
        created_at=now,
        started_at=now,
    )
    db.add(interview)
    await db.flush()
    for index, question in enumerate(frozen_questions, start=1):
        db.add(
            MockInterviewTurn(
                session_id=interview.id,
                position_key=f"{index:02d}",
                question_key=question["key"],
                category=question["category"],
                question=question,
                status="active" if index == 1 else "pending",
            )
        )
    await db.flush()
    return interview


async def get_user_session(
    db: AsyncSession,
    user: User,
    session_id: UUID,
) -> MockInterviewSession:
    interview = await db.get(MockInterviewSession, session_id)
    if interview is None:
        raise LookupError("Mock interview session not found")
    if interview.user_id != user.id:
        raise PermissionError("Mock interview session does not belong to this user")
    return interview


async def _turns(db: AsyncSession, session_id: UUID) -> list[MockInterviewTurn]:
    return list(
        (
            await db.execute(
                select(MockInterviewTurn)
                .where(MockInterviewTurn.session_id == session_id)
                .order_by(MockInterviewTurn.position_key)
            )
        ).scalars()
    )


async def _evaluation_map(
    db: AsyncSession,
    turns: list[MockInterviewTurn],
) -> dict[UUID, MockInterviewTurnEvaluation]:
    if not turns:
        return {}
    result = await db.execute(
        select(MockInterviewTurnEvaluation).where(
            MockInterviewTurnEvaluation.turn_id.in_([turn.id for turn in turns])
        )
    )
    return {item.turn_id: item for item in result.scalars()}


def _evaluation_view(item: MockInterviewTurnEvaluation) -> MockTurnEvaluationView:
    return MockTurnEvaluationView(
        id=item.id,
        rubric_version=item.rubric_version,
        overall_score=item.overall_score,
        dimensions=item.dimensions,
        evidence=item.evidence,
        summary=item.summary,
        next_action=item.next_action,
        created_at=item.created_at,
    )


def _turn_view(
    interview: MockInterviewSession,
    turn: MockInterviewTurn,
    evaluation: MockInterviewTurnEvaluation | None,
) -> MockTurnView:
    guided = interview.mode == "guided"
    practice = interview.mode == "practice"
    hints = [str(item) for item in turn.question.get("hints", [])]
    return MockTurnView(
        id=turn.id,
        position_key=turn.position_key,
        question_key=turn.question_key,
        category=turn.category,
        question=str(turn.question["question"]),
        intent=str(turn.question.get("intent", "")) if guided else None,
        hints=hints if guided else [],
        hint_available=bool(hints) and (guided or practice),
        hint_used=turn.hint_used,
        target_duration_seconds=int(turn.question.get("target_duration_seconds", 60)),
        status=turn.status,
        is_follow_up=turn.is_follow_up,
        parent_turn_id=turn.parent_turn_id,
        follow_up_reason=turn.follow_up_reason,
        speech_attempt_id=turn.speech_attempt_id,
        answer_source=turn.answer_source,
        evaluation=_evaluation_view(evaluation) if evaluation else None,
    )


def _report_view(report: MockReadinessReport) -> MockReadinessReportView:
    return MockReadinessReportView(
        id=report.id,
        rubric_version=report.rubric_version,
        overall_score=report.overall_score,
        confidence=report.confidence,
        dimensions=report.dimensions,
        strengths=report.strengths,
        priorities=report.priorities,
        comparison=report.comparison,
        created_at=report.created_at,
    )


async def session_view(
    db: AsyncSession,
    interview: MockInterviewSession,
) -> MockSessionView:
    turns = await _turns(db, interview.id)
    evaluations = await _evaluation_map(db, turns)
    report = await db.scalar(
        select(MockReadinessReport).where(MockReadinessReport.session_id == interview.id)
    )
    answered = sum(turn.status == "answered" for turn in turns)
    return MockSessionView(
        id=interview.id,
        blueprint_key=interview.blueprint_key,
        blueprint_version=interview.blueprint_version,
        blueprint_checksum=interview.blueprint_checksum,
        mode=interview.mode,
        purpose=interview.purpose,
        status=interview.status,
        current_turn_key=interview.current_turn_key,
        answered_turns=answered,
        total_turns=len(turns),
        turns=[_turn_view(interview, turn, evaluations.get(turn.id)) for turn in turns],
        report=_report_view(report) if report else None,
        created_at=interview.created_at,
        completed_at=interview.completed_at,
    )


async def list_sessions(
    db: AsyncSession,
    user: User,
    *,
    limit: int = 8,
) -> list[MockInterviewSession]:
    result = await db.execute(
        select(MockInterviewSession)
        .where(MockInterviewSession.user_id == user.id)
        .order_by(MockInterviewSession.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def request_hint(
    db: AsyncSession,
    interview: MockInterviewSession,
    turn_id: UUID,
) -> list[str]:
    if interview.mode == "realistic":
        raise PermissionError("Hints are unavailable in realistic mode")
    turn = await _owned_turn(db, interview, turn_id)
    hints = [str(item) for item in turn.question.get("hints", [])]
    turn.hint_used = True
    await db.flush()
    return hints


async def _owned_turn(
    db: AsyncSession,
    interview: MockInterviewSession,
    turn_id: UUID,
) -> MockInterviewTurn:
    turn = await db.get(MockInterviewTurn, turn_id)
    if turn is None or turn.session_id != interview.id:
        raise LookupError("Mock interview turn not found")
    return turn


def _words(text: str) -> list[str]:
    return re.findall(r"[\wÄÖÜäöüß-]+", text.casefold(), flags=re.UNICODE)


def _score_answer(
    turn: MockInterviewTurn,
    text: str,
    *,
    speech_feedback_score: int | None = None,
) -> tuple[int, dict, dict, str, str]:
    normalized = " ".join(text.strip().split())
    lower = normalized.casefold()
    words = _words(normalized)
    word_count = len(words)
    unique_ratio = len(set(words)) / max(1, word_count)

    signal_groups = turn.question.get("required_signals", [])
    matched_groups = [
        group
        for group in signal_groups
        if any(str(candidate).casefold() in lower for candidate in group)
    ]
    coverage = len(matched_groups) / max(1, len(signal_groups))
    relevance = round(30 + 70 * coverage) if signal_groups else 70

    markers = [marker for marker in STRUCTURE_MARKERS if marker in lower]
    structure = min(100, 35 + len(markers) * 18)

    target_duration = int(turn.question.get("target_duration_seconds", 60))
    target_words = max(24, round(target_duration * 1.15))
    distance = abs(word_count - target_words) / max(1, target_words)
    concision = max(20, round(100 - min(1.0, distance) * 80))

    technical_terms = tuple(turn.question.get("technical_terms", [])) + TECHNICAL_TERMS
    matched_technical = sorted({term for term in technical_terms if term in lower})
    has_number = bool(re.search(r"\d", normalized))
    specificity = min(100, 35 + len(matched_technical) * 10 + (20 if has_number else 0))

    filler_count = sum(lower.count(item) for item in FILLERS)
    communication = max(25, min(100, round(55 + unique_ratio * 50 - filler_count * 8)))
    independence = 70 if turn.hint_used else 100

    dimensions: dict[str, int] = {
        "relevance": int(relevance),
        "structure": int(structure),
        "concision": int(concision),
        "specificity": int(specificity),
        "communication": int(communication),
        "independence": int(independence),
    }
    weighted = (
        relevance * 0.32
        + structure * 0.18
        + concision * 0.14
        + specificity * 0.14
        + communication * 0.12
        + independence * 0.10
    )
    if speech_feedback_score is not None:
        dimensions["speech_text_delivery"] = speech_feedback_score
        weighted = weighted * 0.85 + speech_feedback_score * 0.15
    overall = max(0, min(100, round(weighted)))

    evidence = {
        "word_count": word_count,
        "target_words": target_words,
        "matched_signal_groups": len(matched_groups),
        "required_signal_groups": len(signal_groups),
        "structure_markers": markers,
        "technical_terms": matched_technical,
        "filler_count": filler_count,
        "hint_used": turn.hint_used,
    }
    if overall >= 80:
        summary = "Strong answer: relevant, structured and interview-ready for this prompt."
    elif overall >= 65:
        summary = "Usable answer with one or two areas to sharpen before a realistic interview."
    else:
        summary = "The answer needs clearer relevance, structure or concrete evidence before the next rep."
    weakest = min(dimensions, key=dimensions.get)  # type: ignore[arg-type]
    next_actions = {
        "relevance": "Answer the exact question earlier and include the missing required signal.",
        "structure": "Use a visible sequence such as context → action → result.",
        "concision": "Aim closer to the target duration and remove side details.",
        "specificity": "Add one concrete technical decision, example or measurable detail.",
        "communication": "Use shorter sentences and fewer filler words.",
        "independence": "Repeat the question once without opening a hint.",
        "speech_text_delivery": "Repeat at a steadier pace while keeping the same structure.",
    }
    return overall, dimensions, evidence, summary, next_actions[weakest]


async def _insert_follow_up_if_needed(
    db: AsyncSession,
    interview: MockInterviewSession,
    turn: MockInterviewTurn,
    score: int,
) -> None:
    follow_up = turn.question.get("follow_up")
    if turn.is_follow_up or not follow_up:
        return
    threshold = {"guided": 60, "practice": 72, "realistic": 80}[interview.mode]
    if score >= threshold:
        return
    exists = await db.scalar(
        select(MockInterviewTurn.id).where(MockInterviewTurn.parent_turn_id == turn.id)
    )
    if exists is not None:
        return
    db.add(
        MockInterviewTurn(
            session_id=interview.id,
            position_key=f"{turn.position_key}a",
            question_key=str(follow_up["key"]),
            category=turn.category,
            question=follow_up,
            status="pending",
            is_follow_up=True,
            parent_turn_id=turn.id,
            follow_up_reason="clarify_weak_answer",
        )
    )
    await db.flush()


async def _build_report(
    db: AsyncSession,
    interview: MockInterviewSession,
) -> MockReadinessReport:
    existing = await db.scalar(
        select(MockReadinessReport).where(MockReadinessReport.session_id == interview.id)
    )
    if existing is not None:
        return existing
    turns = await _turns(db, interview.id)
    evaluations = await _evaluation_map(db, turns)
    answered = [turn for turn in turns if turn.id in evaluations]
    core = [turn for turn in answered if not turn.is_follow_up]
    category_scores: dict[str, list[int]] = defaultdict(list)
    communication_scores: list[int] = []
    independence_scores: list[int] = []
    for turn in answered:
        evaluation = evaluations[turn.id]
        category_scores[turn.category].append(evaluation.overall_score)
        communication_scores.append(int(evaluation.dimensions.get("communication", 0)))
        independence_scores.append(int(evaluation.dimensions.get("independence", 0)))
    dimensions = {
        category: round(sum(scores) / len(scores))
        for category, scores in category_scores.items()
    }
    dimensions["communication"] = round(
        sum(communication_scores) / max(1, len(communication_scores))
    )
    dimensions["independence"] = round(
        sum(independence_scores) / max(1, len(independence_scores))
    )
    overall = round(
        sum(evaluations[turn.id].overall_score for turn in core) / max(1, len(core))
    )
    planned_core = len(interview.plan.get("questions", []))
    coverage = len(core) / max(1, planned_core)
    speech_core = sum(
        bool(turn.answer_source and turn.answer_source.startswith("speech_provider"))
        for turn in core
    )
    speech_ratio = speech_core / max(1, len(core))
    mode_factor = {"guided": 0.72, "practice": 0.86, "realistic": 1.0}[interview.mode]
    independence_ratio = dimensions["independence"] / 100
    confidence = round(
        min(1.0, coverage * mode_factor * (0.85 + 0.15 * speech_ratio) * (0.9 + 0.1 * independence_ratio)),
        3,
    )
    ranked = sorted(dimensions.items(), key=lambda item: item[1], reverse=True)
    strengths = [
        {"dimension": name, "score": score} for name, score in ranked[:2]
    ]
    priorities = [
        {"dimension": name, "score": score} for name, score in reversed(ranked[-2:])
    ]
    comparison: dict = {}
    if interview.purpose == "final":
        baseline = await db.execute(
            select(MockReadinessReport, MockInterviewSession)
            .join(
                MockInterviewSession,
                MockInterviewSession.id == MockReadinessReport.session_id,
            )
            .where(
                MockInterviewSession.user_id == interview.user_id,
                MockInterviewSession.blueprint_key == interview.blueprint_key,
                MockInterviewSession.mode == interview.mode,
                MockInterviewSession.purpose == "baseline",
                MockInterviewSession.completed_at.is_not(None),
                MockInterviewSession.created_at < interview.created_at,
            )
            .order_by(MockInterviewSession.created_at.desc())
            .limit(1)
        )
        row = baseline.first()
        if row:
            baseline_report = row[0]
            comparison = {
                "baseline_report_id": str(baseline_report.id),
                "baseline_overall_score": baseline_report.overall_score,
                "overall_delta": overall - baseline_report.overall_score,
                "dimension_deltas": {
                    key: int(value) - int(baseline_report.dimensions.get(key, 0))
                    for key, value in dimensions.items()
                },
            }
    report = MockReadinessReport(
        session_id=interview.id,
        rubric_version=1,
        overall_score=overall,
        confidence=confidence,
        dimensions=dimensions,
        strengths=strengths,
        priorities=priorities,
        comparison=comparison,
    )
    db.add(report)
    await db.flush()
    return report


async def _advance(
    db: AsyncSession,
    interview: MockInterviewSession,
) -> None:
    next_turn = await db.scalar(
        select(MockInterviewTurn)
        .where(
            MockInterviewTurn.session_id == interview.id,
            MockInterviewTurn.status == "pending",
        )
        .order_by(MockInterviewTurn.position_key)
        .limit(1)
    )
    if next_turn is not None:
        next_turn.status = "active"
        interview.current_turn_key = next_turn.position_key
        await db.flush()
        return
    interview.status = "completed"
    interview.current_turn_key = None
    interview.completed_at = datetime.now(UTC)
    await _build_report(db, interview)
    await db.flush()


async def _answer_turn(
    db: AsyncSession,
    interview: MockInterviewSession,
    turn: MockInterviewTurn,
    text: str,
    *,
    answer_source: str,
    idempotency_key: str | None,
    speech_feedback_score: int | None = None,
) -> None:
    normalized = " ".join(text.strip().split())
    if not normalized:
        raise ValueError("Interview answer cannot be empty")
    if turn.status == "answered":
        if idempotency_key and turn.answer_idempotency_key == idempotency_key:
            return
        if answer_source.startswith("speech") and turn.speech_attempt_id:
            return
        raise ValueError("This interview turn has already been answered")
    if turn.status not in {"active", "pending"}:
        raise ValueError("This interview turn is not answerable")
    overall, dimensions, evidence, summary, next_action = _score_answer(
        turn,
        normalized,
        speech_feedback_score=speech_feedback_score,
    )
    evaluation = MockInterviewTurnEvaluation(
        turn_id=turn.id,
        rubric_version=1,
        overall_score=overall,
        dimensions=dimensions,
        evidence=evidence,
        summary=summary,
        next_action=next_action,
    )
    db.add(evaluation)
    turn.answer_text = normalized
    turn.answer_source = answer_source
    turn.answer_idempotency_key = idempotency_key
    turn.status = "answered"
    turn.answered_at = datetime.now(UTC)
    await db.flush()
    await _insert_follow_up_if_needed(db, interview, turn, overall)
    await _advance(db, interview)


async def submit_text_answer(
    db: AsyncSession,
    interview: MockInterviewSession,
    turn_id: UUID,
    text: str,
    idempotency_key: str,
) -> None:
    turn = await _owned_turn(db, interview, turn_id)
    await _answer_turn(
        db,
        interview,
        turn,
        text,
        answer_source="text",
        idempotency_key=idempotency_key,
    )


async def create_turn_speech_attempt(
    db: AsyncSession,
    user: User,
    interview: MockInterviewSession,
    turn_id: UUID,
) -> SpeechAttempt:
    await require_consent(db, user)
    turn = await _owned_turn(db, interview, turn_id)
    if turn.status == "answered":
        raise ValueError("This interview turn has already been answered")
    if turn.speech_attempt_id:
        existing = await db.get(SpeechAttempt, turn.speech_attempt_id)
        if existing is not None:
            return existing
    await ensure_starter_learning(db, user)
    enrollment = await get_active_enrollment(db, user.id)
    prompt = {
        "id": turn.question_key,
        "category": turn.category,
        "question": str(turn.question["question"]),
        "support": [],
        "target_duration_seconds": int(turn.question.get("target_duration_seconds", 60)),
    }
    attempt = SpeechAttempt(
        user_id=user.id,
        enrollment_id=enrollment.id if enrollment else None,
        source_kind="mock_interview_turn",
        source_key=f"{interview.id}:{turn.id}",
        prompt=prompt,
        prompt_checksum=_canonical_checksum(prompt),
        language="de",
        target_duration_seconds=prompt["target_duration_seconds"],
        status="created",
    )
    db.add(attempt)
    await db.flush()
    turn.speech_attempt_id = attempt.id
    await db.flush()
    return attempt


async def sync_speech_answer(
    db: AsyncSession,
    user: User,
    interview: MockInterviewSession,
    turn_id: UUID,
) -> None:
    turn = await _owned_turn(db, interview, turn_id)
    if turn.speech_attempt_id is None:
        raise ValueError("This turn has no linked speech attempt")
    attempt = await db.get(SpeechAttempt, turn.speech_attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise PermissionError("Linked speech attempt is unavailable")
    if turn.status == "answered":
        return
    transcripts = list(
        (
            await db.execute(
                select(SpeechTranscript)
                .where(SpeechTranscript.speech_attempt_id == attempt.id)
                .order_by(SpeechTranscript.created_at, SpeechTranscript.revision_number)
            )
        ).scalars()
    )
    if not transcripts:
        raise ValueError("Speech transcript is not ready yet")
    preferred = next(
        (item for item in reversed(transcripts) if item.kind == "learner_corrected"),
        None,
    )
    if preferred is None:
        preferred = next(
            (item for item in reversed(transcripts) if item.kind == "provider_raw"),
            None,
        )
    if preferred is None:
        preferred = transcripts[-1]
    source = {
        "provider_raw": "speech_provider",
        "learner_corrected": "speech_provider_corrected",
        "manual": "speech_manual",
    }.get(preferred.kind, "speech")
    feedback = await db.scalar(
        select(SpeechFeedback)
        .where(SpeechFeedback.transcript_id == preferred.id)
        .order_by(SpeechFeedback.created_at.desc())
        .limit(1)
    )
    await _answer_turn(
        db,
        interview,
        turn,
        preferred.text,
        answer_source=source,
        idempotency_key=None,
        speech_feedback_score=feedback.overall_score if feedback else None,
    )


async def speech_attempt_view_for_turn(
    db: AsyncSession,
    attempt: SpeechAttempt,
):
    return await attempt_view(db, attempt)
