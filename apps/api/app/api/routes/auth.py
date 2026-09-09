from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.users import get_user_by_email

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: EmailStr


def _set_session_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    token = create_access_token(user.id)
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.app_env in {"staging", "production"},
        samesite="lax",
        max_age=settings.access_token_ttl_minutes * 60,
        path="/",
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    session: DbSession,
) -> UserResponse:
    email = str(payload.email).lower()
    if await get_user_by_email(session, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
    )
    session.add(user)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None

    await session.refresh(user)
    _set_session_cookie(response, user)
    return UserResponse(id=str(user.id), email=user.email)


@router.post("/login", response_model=UserResponse)
async def login(payload: LoginRequest, response: Response, session: DbSession) -> UserResponse:
    user = await get_user_by_email(session, str(payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    _set_session_cookie(response, user)
    return UserResponse(id=str(user.id), email=user.email)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.auth_cookie_name, path="/")


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse(id=str(user.id), email=user.email)
