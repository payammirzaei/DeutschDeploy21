from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, EmailStr

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.repositories.users import get_user_by_email

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr


@router.post("/login", response_model=UserResponse)
async def login(payload: LoginRequest, response: Response, session: DbSession) -> UserResponse:
    user = await get_user_by_email(session, str(payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

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
    return UserResponse(id=str(user.id), email=user.email)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.auth_cookie_name, path="/")


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse(id=str(user.id), email=user.email)
