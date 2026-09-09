import structlog

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.db.session import SessionFactory
from app.models.user import User
from app.repositories.users import get_user_by_email

logger = structlog.get_logger()


async def ensure_bootstrap_user() -> None:
    settings = get_settings()
    if not settings.app_bootstrap_email or not settings.app_bootstrap_password:
        logger.warning("bootstrap_user_skipped", reason="credentials_not_configured")
        return

    email = str(settings.app_bootstrap_email).lower()
    password = settings.app_bootstrap_password

    async with SessionFactory() as session:
        existing = await get_user_by_email(session, email)
        if existing:
            if not verify_password(password, existing.password_hash):
                existing.password_hash = hash_password(password)
                await session.commit()
                logger.info("bootstrap_user_password_updated", email=email)
            return

        session.add(
            User(
                email=email,
                password_hash=hash_password(password),
            )
        )
        await session.commit()
        logger.info("bootstrap_user_created", email=email)
