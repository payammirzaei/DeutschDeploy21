import hashlib
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_job import PlatformJob
from app.models.speech import (
    MediaObject,
    ProviderInvocation,
    SpeechAttempt,
    SpeechFeedback,
    SpeechTranscript,
)
from app.services.media_storage import get_media_storage
from app.services.speech_feedback import build_speech_feedback
from app.services.speech_providers import get_speech_to_text_provider


async def process_speech_transcription(
    session: AsyncSession,
    job: PlatformJob,
) -> dict:
    raw_attempt_id = job.payload.get("speech_attempt_id")
    if not raw_attempt_id:
        raise ValueError("speech.transcribe job is missing speech_attempt_id")
    attempt = await session.get(SpeechAttempt, UUID(str(raw_attempt_id)))
    if attempt is None:
        raise ValueError("Speech attempt not found")
    if attempt.media_object_id is None:
        raise ValueError("Speech attempt has no audio")
    media = await session.get(MediaObject, attempt.media_object_id)
    if media is None or media.status != "verified":
        raise ValueError("Speech audio is not available for transcription")

    existing = await session.scalar(
        select(SpeechTranscript).where(
            SpeechTranscript.speech_attempt_id == attempt.id,
            SpeechTranscript.kind == "provider_raw",
        )
    )
    if existing is not None:
        feedback = await session.scalar(
            select(SpeechFeedback)
            .where(SpeechFeedback.transcript_id == existing.id)
            .limit(1)
        )
        attempt.status = "feedback_ready"
        attempt.updated_at = datetime.now(UTC)
        await session.commit()
        return {
            "speech_attempt_id": str(attempt.id),
            "transcript_id": str(existing.id),
            "feedback_id": str(feedback.id) if feedback else None,
            "reused": True,
        }

    provider = get_speech_to_text_provider()
    request_checksum = hashlib.sha256(
        f"{attempt.id}:{media.sha256}:{provider.provider_name}:{provider.model_name}".encode()
    ).hexdigest()
    invocation = ProviderInvocation(
        speech_attempt_id=attempt.id,
        purpose="speech.transcription",
        provider=provider.provider_name,
        model=provider.model_name,
        template_version="v1",
        request_checksum=request_checksum,
        correlation_id=str(uuid4()),
        status="running",
    )
    session.add(invocation)
    attempt.status = "transcribing"
    attempt.updated_at = datetime.now(UTC)
    await session.commit()

    started = time.monotonic()
    try:
        storage = get_media_storage()
        async with storage.open_local(media.storage_key) as audio_path:
            result = await provider.transcribe(
                audio_path,
                media.content_type,
            )
        transcript = SpeechTranscript(
            speech_attempt_id=attempt.id,
            kind="provider_raw",
            revision_number=1,
            text=result.text,
            language=result.language or "de",
            provider=result.provider,
            model=result.model,
            confidence=result.confidence,
        )
        session.add(transcript)
        await session.flush()
        feedback = build_speech_feedback(
            attempt,
            transcript,
            duration_ms=media.duration_ms,
        )
        session.add(feedback)
        await session.flush()

        invocation.status = "succeeded"
        invocation.latency_ms = result.latency_ms
        invocation.retained_output_ref = str(transcript.id)
        invocation.finished_at = datetime.now(UTC)
        attempt.status = "feedback_ready"
        attempt.updated_at = datetime.now(UTC)
        await session.commit()
        return {
            "speech_attempt_id": str(attempt.id),
            "transcript_id": str(transcript.id),
            "feedback_id": str(feedback.id),
            "provider": result.provider,
            "model": result.model,
            "reused": False,
        }
    except Exception as exc:
        invocation.status = "failed"
        invocation.latency_ms = max(1, int((time.monotonic() - started) * 1000))
        invocation.error_code = type(exc).__name__[:100]
        invocation.finished_at = datetime.now(UTC)
        attempt.status = "failed"
        attempt.updated_at = datetime.now(UTC)
        await session.commit()
        raise
