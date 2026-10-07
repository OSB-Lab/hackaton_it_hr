import logging
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.modules.auth.mailer import send_verification_email
from app.modules.auth.schemas import (
    RegisterRequest, UserResponse, VerifyEmailRequest, VerifyEmailResponse,
)
from app.modules.auth.security import (
    InvalidTokenError, create_email_verification_token,
)
from app.modules.auth.service import (
    AuthPersistenceError, EmailAlreadyRegistered, register_user, verify_email,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


AuthSession = Annotated[Session, Depends(get_auth_session)]


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, session: AuthSession) -> UserResponse:
    try:
        user = register_user(session, request)
    except EmailAlreadyRegistered:
        raise HTTPException(status_code=409, detail="Email already registered") from None
    except AuthPersistenceError:
        raise HTTPException(status_code=503, detail="Registration unavailable") from None

    # SessionLocal has expire_on_commit=False: these reads do not reopen a
    # transaction. SMTP starts only after the user has been committed.
    response = UserResponse.model_validate(user)
    token = create_email_verification_token(user.id)
    if not send_verification_email(user.email, token):
        logger.warning("Verification email delivery failed for user_id=%s", user.id)
    return response


@router.post("/verify-email", response_model=VerifyEmailResponse)
def verify_email_address(request: VerifyEmailRequest, session: AuthSession) -> VerifyEmailResponse:
    try:
        verify_email(session, request.token)
    except InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid verification token") from None
    except AuthPersistenceError:
        raise HTTPException(status_code=503, detail="Email verification unavailable") from None
    return VerifyEmailResponse()
