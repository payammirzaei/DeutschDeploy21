import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.platform_job import PlatformJob
from app.models.speech import (
    MediaObject,
    SpeechAttempt,
    SpeechConsent,
    SpeechFeedback,
    SpeechTranscript,
)
from app.models.user import User
from app.schemas.speech import (
    MediaView,
    SpeakingPromptView,
    SpeechAttemptView,
    SpeechConsentView,
    SpeechFeedbackView,
    TranscriptView,
)
from app.services.jobs import enqueue_job_signal
from app.services.learning import ensure_starter_learning, get_active_enrollment
from app.services.media_storage import get_media_storage
from app.services.speech_feedback import build_speech_feedback

ALLOWED_AUDIO_TYPES = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}


def load_speaking_prompts() -> list[dict]:
    path = Path(__file__).resolve().parents[4] / "content" / "speaking-prompts.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("Speaking prompt catalog must be a list")
    seen: set[str] = set()
    for item in payload:
        required = {"id", "category", "question", "support", "target_duration_seconds"}
        if not isinstance(item, dict) or not required.issubset(item):
            raise RuntimeError("Speaking prompt catalog contains an invalid entry")
        prompt_id = str(item["id"])
        if prompt_id in seen:
            raise RuntimeError(f"Duplicate speaking prompt id: {prompt_id}")
        if not isinstance(item["support"], list):
            raise RuntimeError(f"Speaking prompt support must be a list: {prompt_id}")
        duration = int(item["target_duration_seconds"])
        if not 15 <= duration <= 180:
            raise RuntimeError(f"Invalid target duration for speaking prompt: {prompt_id}")
        seen.add(prompt_id)
    return payload


def speaking_prompt_views() -> list[SpeakingPromptView]:
    return [SpeakingPromptView.model_validate(item) for item in load_speaking_prompts()]


def _prompt_by_id(prompt_id: str) -> dict:
    for prompt in load_speaking_prompts():
        if prompt["id"] == prompt_id:
            return prompt
    raise LookupError("Speaking prompt not found")


async def get_consent(session: AsyncSession, user: User) -> SpeechConsentView:
    settings = get_settings()
    consent = await session.scalar(
        select(SpeechConsent)
        .where(
            SpeechConsent.user_id == user.id,
            SpeechConsent.policy_version == settings.speech_consent_version,
        )
        .order_by(SpeechConsent.accepted_at.desc())
        .limit(1)
    )
    accepted = bool(consent and consent.revoked_at is None)
    return SpeechConsentView(
        policy_version=settings.speech_consent_version,
        accepted=accepted,
        accepted_at=consent.accepted_at if accepted and consent else None,
    )


async def set_consent(session: AsyncSession, user: User, accepted: bool) -> SpeechConsentView:
    settings = get_settings()
    consent = await session.scalar(
        select(SpeechConsent).where(
            SpeechConsent.user_id == user.id,
            SpeechConsent.policy_version == settings.speech_consent_version,
        )
    )
    now = datetime.now(UTC)
    if accepted:
        if consent is None:
            consent = SpeechConsent(
                user_id=user.id,
                policy_version=settings.speech_consent_version,
                accepted_at=now,
            )
            session.add(consent)
        else:
            consent.accepted_at = now
            consent.revoked_at = None
    elif consent is not None:
        consent.revoked_at = now
    await session.flush()
    return await get_consent(session, user)


async def require_consent(session: AsyncSession, user: User) -> None:
    consent = await get_consent(session, user)
    if not consent.accepted:
        raise PermissionError("Speech recording consent is required")


async def create_speech_attempt(
    session: AsyncSession,
    user: User,
    prompt_id: str,
) -> SpeechAttempt:
    await require_consent(session, user)
    await ensure_starter_learning(session, user)
    enrollment = await get_active_enrollment(session, user.id)
    prompt = _prompt_by_id(prompt_id)
    frozen = {
        "id": str(prompt["id"]),
        "category": str(prompt["category"]),
        "question": str(prompt["question"]),
        "support": [str(value) for value in prompt["support"]],
        "target_duration_seconds": int(prompt["target_duration_seconds"]),
    }
    checksum = hashlib.sha256(
        json.dumps(frozen, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    attempt = SpeechAttempt(
        user_id=user.id,
        enrollment_id=enrollment.id if enrollment else None,
        source_kind="speaking_prompt",
        source_key=prompt_id,
        prompt=frozen,
        prompt_checksum=checksum,
        language="de",
        target_duration_seconds=int(prompt["target_duration_seconds"]),
        status="created",
    )
    session.add(attempt)
    await session.flush()
    return attempt


async def get_user_attempt(
    session: AsyncSession,
    user: User,
    attempt_id: UUID,
) -> SpeechAttempt:
    attempt = await session.get(SpeechAttempt, attempt_id)
    if attempt is None:
        raise LookupError("Speech attempt not found")
    if attempt.user_id != user.id:
        raise PermissionError("Speech attempt does not belong to this user")
    return attempt


async def upload_audio(
    session: AsyncSession,
    user: User,
    attempt: SpeechAttempt,
    request: Request,
    *,
    duration_ms: int | None,
) -> PlatformJob:
    await require_consent(session, user)
    if attempt.media_object_id is not None:
        raise ValueError("This speech attempt already has an audio object")
    if attempt.status not in {"created", "failed"}:
        raise ValueError(f"Audio cannot be uploaded while attempt is {attempt.status}")

    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    extension = ALLOWED_AUDIO_TYPES.get(content_type)
    if extension is None:
        raise ValueError("Unsupported audio content type")
    if duration_ms is not None and not 500 <= duration_ms <= 180_000:
        raise ValueError("Audio duration must be between 0.5 and 180 seconds")

    storage_key = f"{uuid4().hex[:2]}/{uuid4().hex}{extension}"
    storage = get_media_storage()
    settings = get_settings()
    byte_size, checksum = await storage.save_stream(
        storage_key,
        request.stream(),
        max_bytes=settings.media_max_audio_bytes,
    )

    media = MediaObject(
        user_id=user.id,
        storage_backend=storage.backend_name,
        storage_key=storage_key,
        status="verified",
        content_type=content_type,
        byte_size=byte_size,
        sha256=checksum,
        duration_ms=duration_ms,
        finalized_at=datetime.now(UTC),
    )
    session.add(media)
    await session.flush()

    job = PlatformJob(
        job_type="speech.transcribe",
        schema_version=1,
        idempotency_key=f"speech-transcribe:{attempt.id}:{checksum}",
        payload={"speech_attempt_id": str(attempt.id)},
    )
    session.add(job)
    await session.flush()

    attempt.media_object_id = media.id
    attempt.transcription_job_id = job.id
    attempt.status = "queued"
    attempt.updated_at = datetime.now(UTC)
    await session.commit()
    await enqueue_job_signal(job.id)
    return job


async def retry_transcription(
    session: AsyncSession,
    user: User,
    attempt: SpeechAttempt,
) -> PlatformJob:
    await require_consent(session, user)
    if attempt.media_object_id is None:
        raise ValueError("Cannot retry transcription without audio")
    raw = await session.scalar(
        select(SpeechTranscript.id).where(
            SpeechTranscript.speech_attempt_id == attempt.id,
            SpeechTranscript.kind == "provider_raw",
        )
    )
    if raw is not None:
        raise ValueError("A provider transcript already exists for this attempt")
    attempt.transcription_retry_count += 1
    job = PlatformJob(
        job_type="speech.transcribe",
        schema_version=1,
        idempotency_key=(
            f"speech-transcribe:{attempt.id}:retry:{attempt.transcription_retry_count}"
        ),
        payload={"speech_attempt_id": str(attempt.id)},
    )
    session.add(job)
    await session.flush()
    attempt.transcription_job_id = job.id
    attempt.status = "queued"
    attempt.updated_at = datetime.now(UTC)
    await session.commit()
    await enqueue_job_signal(job.id)
    return job


async def add_manual_transcript(
    session: AsyncSession,
    user: User,
    attempt: SpeechAttempt,
    text: str,
) -> SpeechTranscript:
    await require_consent(session, user)
    if attempt.status not in {"created", "failed", "feedback_ready"}:
        raise ValueError("Manual transcript cannot be added in the current state")
    return await _add_corrected_transcript(session, attempt, text, kind="manual")


async def correct_transcript(
    session: AsyncSession,
    user: User,
    attempt: SpeechAttempt,
    text: str,
) -> SpeechTranscript:
    await require_consent(session, user)
    exists = await session.scalar(
        select(SpeechTranscript.id).where(
            SpeechTranscript.speech_attempt_id == attempt.id,
            SpeechTranscript.kind.in_(["provider_raw", "learner_corrected", "manual"]),
        )
    )
    if exists is None:
        raise ValueError("There is no transcript to correct yet")
    return await _add_corrected_transcript(
        session,
        attempt,
        text,
        kind="learner_corrected",
    )


async def _add_corrected_transcript(
    session: AsyncSession,
    attempt: SpeechAttempt,
    text: str,
    *,
    kind: str,
) -> SpeechTranscript:
    normalized = " ".join(text.strip().split())
    if not normalized:
        raise ValueError("Transcript cannot be empty")
    latest_revision = await session.scalar(
        select(func.max(SpeechTranscript.revision_number)).where(
            SpeechTranscript.speech_attempt_id == attempt.id,
            SpeechTranscript.kind == kind,
        )
    )
    transcript = SpeechTranscript(
        speech_attempt_id=attempt.id,
        kind=kind,
        revision_number=int(latest_revision or 0) + 1,
        text=normalized,
        language="de",
        provider=None,
        model=None,
    )
    session.add(transcript)
    await session.flush()
    await _create_feedback(session, attempt, transcript)
    attempt.status = "feedback_ready"
    attempt.updated_at = datetime.now(UTC)
    await session.commit()
    return transcript


async def _create_feedback(
    session: AsyncSession,
    attempt: SpeechAttempt,
    transcript: SpeechTranscript,
) -> SpeechFeedback:
    media = (
        await session.get(MediaObject, attempt.media_object_id)
        if attempt.media_object_id
        else None
    )
    feedback = build_speech_feedback(
        attempt,
        transcript,
        duration_ms=media.duration_ms if media else None,
    )
    session.add(feedback)
    await session.flush()
    return feedback


async def delete_audio(
    session: AsyncSession,
    user: User,
    attempt: SpeechAttempt,
) -> None:
    if attempt.media_object_id is None:
        return
    media = await session.get(MediaObject, attempt.media_object_id)
    if media is None or media.user_id != user.id:
        raise PermissionError("Audio object does not belong to this user")
    if media.status != "deleted":
        await get_media_storage().delete(media.storage_key)
        media.status = "deleted"
        media.deleted_at = datetime.now(UTC)
        await session.commit()


async def list_attempts(
    session: AsyncSession,
    user: User,
    *,
    limit: int,
) -> list[SpeechAttempt]:
    return list(
        (
            await session.execute(
                select(SpeechAttempt)
                .where(SpeechAttempt.user_id == user.id)
                .order_by(SpeechAttempt.created_at.desc())
                .limit(limit)
            )
        ).scalars()
    )


async def attempt_view(session: AsyncSession, attempt: SpeechAttempt) -> SpeechAttemptView:
    media = (
        await session.get(MediaObject, attempt.media_object_id)
        if attempt.media_object_id
        else None
    )
    transcripts = list(
        (
            await session.execute(
                select(SpeechTranscript)
                .where(SpeechTranscript.speech_attempt_id == attempt.id)
                .order_by(SpeechTranscript.created_at, SpeechTranscript.revision_number)
            )
        ).scalars()
    )
    feedback = await session.scalar(
        select(SpeechFeedback)
        .where(SpeechFeedback.speech_attempt_id == attempt.id)
        .order_by(SpeechFeedback.created_at.desc())
        .limit(1)
    )
    return SpeechAttemptView(
        id=attempt.id,
        source_key=attempt.source_key,
        prompt=attempt.prompt,
        prompt_checksum=attempt.prompt_checksum,
        language=attempt.language,
        target_duration_seconds=attempt.target_duration_seconds,
        status=attempt.status,
        media=(
            MediaView(
                id=media.id,
                status=media.status,
                content_type=media.content_type,
                byte_size=media.byte_size,
                sha256=media.sha256,
                duration_ms=media.duration_ms,
            )
            if media
            else None
        ),
        transcription_job_id=attempt.transcription_job_id,
        transcription_retry_count=attempt.transcription_retry_count,
        transcripts=[
            TranscriptView(
                id=item.id,
                kind=item.kind,
                revision_number=item.revision_number,
                text=item.text,
                language=item.language,
                provider=item.provider,
                model=item.model,
                confidence=item.confidence,
                created_at=item.created_at,
            )
            for item in transcripts
        ],
        feedback=(
            SpeechFeedbackView(
                id=feedback.id,
                transcript_id=feedback.transcript_id,
                evaluator_type=feedback.evaluator_type,
                evaluator_version=feedback.evaluator_version,
                overall_score=feedback.overall_score,
                summary=feedback.summary,
                dimensions=feedback.dimensions,
                corrections=feedback.corrections,
                next_action=feedback.next_action,
                created_at=feedback.created_at,
            )
            if feedback
            else None
        ),
        created_at=attempt.created_at,
        updated_at=attempt.updated_at,
    )
