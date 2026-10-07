from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.user import User
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.auth.security import (
    InvalidTokenError, decode_email_verification_token, hash_password, verify_password,
)


class EmailAlreadyRegistered(Exception):
    pass


class AuthPersistenceError(Exception):
    pass


class InvalidCredentials(Exception):
    pass


def authenticate_user(session: Session, request: LoginRequest) -> User:
    try:
        user = session.scalar(select(User).where(func.lower(User.email) == request.email))
    except SQLAlchemyError:
        session.rollback()
        raise AuthPersistenceError from None
    if user is None or not verify_password(request.password, user.password_hash):
        raise InvalidCredentials
    return user


def register_user(session: Session, request: RegisterRequest) -> User:
    try:
        # Also recognise legacy rows with mixed-case email. All new API writes
        # use the shared normalized schema value and the existing unique index.
        existing = session.scalar(
            select(User.id).where(func.lower(User.email) == request.email)
        )
        if existing is not None:
            session.rollback()
            raise EmailAlreadyRegistered

        user = User(
            email=request.email,
            password_hash=hash_password(request.password),
            role=request.role,
            is_verified=False,
        )
        session.add(user)
        session.commit()
        return user
    except IntegrityError as error:
        session.rollback()
        original = error.orig
        if (
            getattr(original, "sqlstate", None) == "23505"
            and getattr(getattr(original, "diag", None), "constraint_name", None)
            == "ix_users_email"
        ):
            raise EmailAlreadyRegistered from None
        raise AuthPersistenceError from None
    except SQLAlchemyError:
        session.rollback()
        raise AuthPersistenceError from None


def verify_email(session: Session, token: str) -> None:
    user_id = decode_email_verification_token(token)
    try:
        user = session.get(User, user_id)
        if user is None:
            session.rollback()
            raise InvalidTokenError("Invalid verification token")
        user.is_verified = True
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise AuthPersistenceError from None
