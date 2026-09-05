from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from payops_core.auth.emailer import EmailSender
from payops_core.auth.policy import password_errors, validate_signup
from payops_core.config import Settings
from payops_core.data.models import AuthUser
from payops_core.models.auth import (
    AuthSuccessResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ProfileUpdateRequest,
    PublicUser,
    ResetPasswordRequest,
    SignupRequest,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.auth_service import (
    authenticate,
    change_password,
    create_user,
    get_user_by_email,
    issue_session,
    request_password_reset,
    reset_password,
    revoke_session,
)
from apps.api.cookies import clear_session_cookie, set_session_cookie
from apps.api.deps import get_app_settings, get_current_user, get_email_sender, get_session

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_RESET = "If an account exists for this email, you'll receive reset instructions."


def _public_user(user: AuthUser) -> PublicUser:
    return PublicUser(
        user_id=user.user_id,
        name=user.name,
        email=user.email,
        role=user.role,  # type: ignore[arg-type]
        status=user.status,  # type: ignore[arg-type]
        created_at=user.created_at,
        last_active_at=user.last_active_at,
        last_login_at=user.last_login_at,
    )


@router.post("/signup", response_model=AuthSuccessResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> AuthSuccessResponse:
    errors = validate_signup(
        payload.name,
        payload.email,
        payload.password,
        payload.confirm_password,
        settings.password_min_length,
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors[0])
    if get_user_by_email(session, payload.email) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    try:
        user = create_user(
            session,
            name=payload.name,
            email=payload.email,
            password=payload.password,
            role="user",
        )
        token = issue_session(session, user, settings, request.headers.get("user-agent"))
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        ) from exc
    set_session_cookie(response, token, settings)
    return AuthSuccessResponse(user=_public_user(user))


@router.post("/login", response_model=AuthSuccessResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> AuthSuccessResponse:
    user, token_or_reason = authenticate(
        session,
        payload.email,
        payload.password,
        settings,
        request.headers.get("user-agent"),
    )
    if user is None:
        session.commit()
        if token_or_reason == "suspended":
            raise HTTPException(status_code=403, detail="This account is suspended.")
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    session.commit()
    set_session_cookie(response, token_or_reason, settings)
    return AuthSuccessResponse(user=_public_user(user))


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
    user: AuthUser = Depends(get_current_user),
) -> MessageResponse:
    revoke_session(session, request.cookies.get(settings.cookie_name), user.user_id)
    session.commit()
    clear_session_cookie(response, settings)
    return MessageResponse(message="Signed out.")


@router.get("/me", response_model=PublicUser)
def me(user: AuthUser = Depends(get_current_user)) -> PublicUser:
    return _public_user(user)


@router.patch("/me", response_model=PublicUser)
def update_me(
    payload: ProfileUpdateRequest,
    session: Session = Depends(get_session),
    user: AuthUser = Depends(get_current_user),
) -> PublicUser:
    user.name = payload.name.strip()
    session.commit()
    session.refresh(user)
    return _public_user(user)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
    sender: EmailSender = Depends(get_email_sender),
) -> MessageResponse:
    request_password_reset(session, payload.email, settings, sender)
    session.commit()
    return MessageResponse(message=GENERIC_RESET)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password_route(
    payload: ResetPasswordRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> MessageResponse:
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=422, detail="Passwords do not match.")
    issues = password_errors(payload.password, settings.password_min_length)
    if issues:
        raise HTTPException(status_code=422, detail=issues[0])
    if not reset_password(session, payload.token, payload.password):
        session.commit()
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")
    session.commit()
    return MessageResponse(message="Password updated. You can sign in with your new password.")


@router.post("/change-password", response_model=MessageResponse)
def change_password_route(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
    user: AuthUser = Depends(get_current_user),
) -> MessageResponse:
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=422, detail="Passwords do not match.")
    issues = password_errors(payload.password, settings.password_min_length)
    if issues:
        raise HTTPException(status_code=422, detail=issues[0])
    if not change_password(session, user, payload.current_password, payload.password):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    token = issue_session(session, user, settings, request.headers.get("user-agent"))
    session.commit()
    set_session_cookie(response, token, settings)
    return MessageResponse(message="Password updated.")
