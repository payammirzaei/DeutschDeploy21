import structlog

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionFactory
from app.models.user import User
from app.repositories.users import get_user_by_email

logger = structlog.get_logger()


async def ensure_bootstrap_user() -> None:
    settings = get_settings()
    if not settings.app_bootstrap_email or not settings.app_bootstrap_password:
        logger.warning("bootstrap_user_skipped", reason="credentials_not_configured")
        return

    async with SessionFactory() as session:
        existing = await get_user_by_email(session, str(settings.app_bootstrap_email))
        if existing:
            return
        session.add(
            User(
                email=str(settings.app_bootstrap_email).lower(),
                password_hash=hash_password(settings.app_bootstrap_password),
            )
        )
        await session.commit()
        logger.info("bootstrap_user_created", email=str(settings.app_bootstrap_email).lower())
