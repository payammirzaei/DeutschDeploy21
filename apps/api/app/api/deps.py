from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models.user import User

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=160),
]


async def get_current_user(request: Request, session: DbSession) -> User:
    settings = get_settings()
    session_cookie = request.cookies.get(settings.auth_cookie_name)
    if not session_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    try:
        user_id = decode_access_token(session_cookie)
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session"
        ) from None
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
