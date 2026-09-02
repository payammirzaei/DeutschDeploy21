import asyncio

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.repositories.users import get_user_by_email
from app.services.bootstrap import ensure_bootstrap_user
from app.services.content import apply_verb_import, list_draft_verbs, load_starter_verbs, publish_item


async def seed() -> None:
    await ensure_bootstrap_user()
    settings = get_settings()
    if not settings.app_bootstrap_email:
        raise RuntimeError("APP_BOOTSTRAP_EMAIL is required to seed content")

    async with SessionFactory() as session:
        user = await get_user_by_email(session, str(settings.app_bootstrap_email).lower())
        if user is None:
            raise RuntimeError("bootstrap user was not created")

        payloads = load_starter_verbs()
        imported = await apply_verb_import(session, user, payloads)
        drafts = await list_draft_verbs(session)
        published = 0
        for draft in drafts:
            result = await publish_item(session, user, draft.item_id)
            if not result.reused_existing_version:
                published += 1
        await session.commit()

    print(
        f"starter catalog ready: {len(payloads)} verbs, "
        f"{imported.imported} imported, {published} published"
    )


if __name__ == "__main__":
    asyncio.run(seed())
