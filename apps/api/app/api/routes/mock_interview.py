from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession, IdempotencyKey
from app.schemas.mock_interview import (
    MockBlueprintView,
    MockHintView,
    MockSessionCreateIn,
    MockSessionList,
    MockSessionView,
    MockSpeechAttemptView,
    MockTextAnswerIn,
)
from app.services.mock_interview import (
    blueprint_view,
    create_session,
    create_turn_speech_attempt,
    get_user_session,
    list_sessions,
    request_hint,
    session_view,
    speech_attempt_view_for_turn,
    submit_text_answer,
    sync_speech_answer,
)

router = APIRouter(prefix="/mock-interviews", tags=["mock-interviews"])


@router.get("/blueprint", response_model=MockBlueprintView)
async def blueprint(_user: CurrentUser) -> MockBlueprintView:
    return blueprint_view()


@router.post(
    "/sessions",
    response_model=MockSessionView,
    status_code=status.HTTP_201_CREATED,
)
async def start_session(
    payload: MockSessionCreateIn,
    user: CurrentUser,
    db: DbSession,
) -> MockSessionView:
    try:
        interview = await create_session(db, user, payload)
        await db.commit()
        return await session_view(db, interview)
    except (RuntimeError, ValueError) as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/sessions", response_model=MockSessionList)
async def recent_sessions(
    user: CurrentUser,
    db: DbSession,
    limit: int = 8,
) -> MockSessionList:
    interviews = await list_sessions(db, user, limit=min(20, max(1, limit)))
    return MockSessionList(
        sessions=[await session_view(db, interview) for interview in interviews]
    )


@router.get("/sessions/{session_id}", response_model=MockSessionView)
async def read_session(
    session_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> MockSessionView:
    try:
        interview = await get_user_session(db, user, session_id)
        return await session_view(db, interview)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/sessions/{session_id}/turns/{turn_id}/hint",
    response_model=MockHintView,
)
async def reveal_hint(
    session_id: UUID,
    turn_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> MockHintView:
    try:
        interview = await get_user_session(db, user, session_id)
        hints = await request_hint(db, interview, turn_id)
        await db.commit()
        return MockHintView(hints=hints)
    except LookupError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        await db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/sessions/{session_id}/turns/{turn_id}/text",
    response_model=MockSessionView,
)
async def answer_text(
    session_id: UUID,
    turn_id: UUID,
    payload: MockTextAnswerIn,
    user: CurrentUser,
    db: DbSession,
    idempotency_key: IdempotencyKey,
) -> MockSessionView:
    try:
        interview = await get_user_session(db, user, session_id)
        await submit_text_answer(db, interview, turn_id, payload.text, idempotency_key)
        await db.commit()
        return await session_view(db, interview)
    except LookupError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        await db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/sessions/{session_id}/turns/{turn_id}/speech-attempt",
    response_model=MockSpeechAttemptView,
    status_code=status.HTTP_201_CREATED,
)
async def create_speech_turn(
    session_id: UUID,
    turn_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> MockSpeechAttemptView:
    try:
        interview = await get_user_session(db, user, session_id)
        attempt = await create_turn_speech_attempt(db, user, interview, turn_id)
        await db.commit()
        return MockSpeechAttemptView(
            speech_attempt=await speech_attempt_view_for_turn(db, attempt)
        )
    except LookupError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        await db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/sessions/{session_id}/turns/{turn_id}/sync-speech",
    response_model=MockSessionView,
)
async def sync_speech_turn(
    session_id: UUID,
    turn_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> MockSessionView:
    try:
        interview = await get_user_session(db, user, session_id)
        await sync_speech_answer(db, user, interview, turn_id)
        await db.commit()
        return await session_view(db, interview)
    except LookupError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        await db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
