from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.content import (
    DraftVerbView,
    ImportApplyResult,
    PublishResult,
    VerbImportIn,
    VerbImportReport,
    VerbView,
    VersionSummary,
)
from app.services.content import (
    apply_verb_import,
    dry_run_verbs,
    list_draft_verbs,
    list_published_verbs,
    list_versions,
    load_starter_verbs,
    publish_item,
)

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/verbs", response_model=list[VerbView])
async def get_published_verbs(_: CurrentUser, session: DbSession) -> list[VerbView]:
    return await list_published_verbs(session)


@router.get("/drafts/verbs", response_model=list[DraftVerbView])
async def get_draft_verbs(_: CurrentUser, session: DbSession) -> list[DraftVerbView]:
    return await list_draft_verbs(session)


@router.post("/import/verbs/dry-run", response_model=VerbImportReport)
async def dry_run_import(
    payloads: list[VerbImportIn],
    _: CurrentUser,
    session: DbSession,
) -> VerbImportReport:
    try:
        return await dry_run_verbs(session, payloads)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/import/verbs/apply", response_model=ImportApplyResult)
async def apply_import(
    payloads: list[VerbImportIn],
    user: CurrentUser,
    session: DbSession,
) -> ImportApplyResult:
    try:
        result = await apply_verb_import(session, user, payloads)
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/items/{item_id}/publish", response_model=PublishResult)
async def publish_content_item(
    item_id: UUID,
    user: CurrentUser,
    session: DbSession,
) -> PublishResult:
    try:
        result = await publish_item(session, user, item_id)
        await session.commit()
        return result
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/items/{item_id}/versions", response_model=list[VersionSummary])
async def get_content_versions(
    item_id: UUID,
    _: CurrentUser,
    session: DbSession,
) -> list[VersionSummary]:
    return await list_versions(session, item_id)


@router.post("/starter-catalog", response_model=dict[str, int])
async def install_starter_catalog(
    user: CurrentUser,
    session: DbSession,
) -> dict[str, int]:
    payloads = load_starter_verbs()
    try:
        import_result = await apply_verb_import(session, user, payloads)
        starter_ids = {payload.external_id for payload in payloads}
        drafts = [
            draft
            for draft in await list_draft_verbs(session)
            if draft.external_id in starter_ids
        ]
        published = 0
        for draft in drafts:
            result = await publish_item(session, user, draft.item_id)
            if not result.reused_existing_version:
                published += 1
        await session.commit()
        return {
            "catalog_size": len(payloads),
            "imported": import_result.imported,
            "published": published,
            "unchanged": import_result.unchanged,
        }
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
