from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.speech import (
    SpeakingPromptView,
    SpeechAttemptCreateIn,
    SpeechAttemptList,
    SpeechAttemptView,
    SpeechConsentIn,
    SpeechConsentView,
    SpeechUploadResult,
    TranscriptTextIn,
)
from app.services.media_storage import MediaTooLargeError
from app.services.speech import (
    add_manual_transcript,
    attempt_view,
    correct_transcript,
    create_speech_attempt,
    delete_audio,
    get_consent,
    get_user_attempt,
    list_attempts,
    retry_transcription,
    set_consent,
    speaking_prompt_views,
    upload_audio,
)

router = APIRouter(prefix="/speech", tags=["speech"])


@router.get("/prompts", response_model=list[SpeakingPromptView])
async def prompts(_user: CurrentUser) -> list[SpeakingPromptView]:
    return speaking_prompt_views()


@router.get("/consent", response_model=SpeechConsentView)
async def consent_status(user: CurrentUser, session: DbSession) -> SpeechConsentView:
    return await get_consent(session, user)


@router.post("/consent", response_model=SpeechConsentView)
async def update_consent(
    payload: SpeechConsentIn,
    user: CurrentUser,
    session: DbSession,
) -> SpeechConsentView:
    result = await set_consent(session, user, payload.accepted)
    await session.commit()
    return result


@router.post(
    "/attempts",
    response_model=SpeechAttemptView,
    status_code=status.HTTP_201_CREATED,
)
async def create_attempt(
    payload: SpeechAttemptCreateIn,
    user: CurrentUser,
    session: DbSession,
) -> SpeechAttemptView:
    try:
        attempt = await create_speech_attempt(session, user, payload.prompt_id)
        await session.commit()
        return await attempt_view(session, attempt)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        await session.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/attempts", response_model=SpeechAttemptList)
async def recent_attempts(
    user: CurrentUser,
    session: DbSession,
    limit: int = 8,
) -> SpeechAttemptList:
    bounded = min(25, max(1, limit))
    attempts = await list_attempts(session, user, limit=bounded)
    return SpeechAttemptList(
        attempts=[await attempt_view(session, attempt) for attempt in attempts]
    )


@router.get("/attempts/{attempt_id}", response_model=SpeechAttemptView)
async def read_attempt(
    attempt_id: UUID,
    user: CurrentUser,
    session: DbSession,
) -> SpeechAttemptView:
    try:
        attempt = await get_user_attempt(session, user, attempt_id)
        return await attempt_view(session, attempt)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.put(
    "/attempts/{attempt_id}/audio",
    response_model=SpeechUploadResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_attempt_audio(
    attempt_id: UUID,
    request: Request,
    user: CurrentUser,
    session: DbSession,
    duration_ms: int | None = Header(
        default=None,
        alias="X-Audio-Duration-Ms",
        ge=0,
        le=180_000,
    ),
) -> SpeechUploadResult:
    try:
        attempt = await get_user_attempt(session, user, attempt_id)
        await upload_audio(
            session,
            user,
            attempt,
            request,
            duration_ms=duration_ms,
        )
        await session.refresh(attempt)
        return SpeechUploadResult(
            attempt=await attempt_view(session, attempt),
            queued=True,
        )
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        await session.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MediaTooLargeError as exc:
        await session.rollback()
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/attempts/{attempt_id}/retry-transcription",
    response_model=SpeechAttemptView,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_attempt_transcription(
    attempt_id: UUID,
    user: CurrentUser,
    session: DbSession,
) -> SpeechAttemptView:
    try:
        attempt = await get_user_attempt(session, user, attempt_id)
        await retry_transcription(session, user, attempt)
        await session.refresh(attempt)
        return await attempt_view(session, attempt)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        await session.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/attempts/{attempt_id}/manual-transcript",
    response_model=SpeechAttemptView,
)
async def manual_transcript(
    attempt_id: UUID,
    payload: TranscriptTextIn,
    user: CurrentUser,
    session: DbSession,
) -> SpeechAttemptView:
    try:
        attempt = await get_user_attempt(session, user, attempt_id)
        await add_manual_transcript(session, user, attempt, payload.text)
        await session.refresh(attempt)
        return await attempt_view(session, attempt)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        await session.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/attempts/{attempt_id}/correct-transcript",
    response_model=SpeechAttemptView,
)
async def correct_attempt_transcript(
    attempt_id: UUID,
    payload: TranscriptTextIn,
    user: CurrentUser,
    session: DbSession,
) -> SpeechAttemptView:
    try:
        attempt = await get_user_attempt(session, user, attempt_id)
        await correct_transcript(session, user, attempt, payload.text)
        await session.refresh(attempt)
        return await attempt_view(session, attempt)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        await session.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete(
    "/attempts/{attempt_id}/audio",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_attempt_audio(
    attempt_id: UUID,
    user: CurrentUser,
    session: DbSession,
) -> None:
    try:
        attempt = await get_user_attempt(session, user, attempt_id)
        await delete_audio(session, user, attempt)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        await session.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
