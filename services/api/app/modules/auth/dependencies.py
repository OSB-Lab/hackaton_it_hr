from collections.abc import Callable, Coroutine, Iterator
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import SessionLocal

from app.models.user import User
from app.modules.auth.schemas import AuthRole
from app.modules.auth.security import InvalidTokenError, decode_access_token


def get_auth_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


AuthSession = Annotated[Session, Depends(get_auth_session)]
bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: AuthSession,
) -> User:
    """Validate an access token and load the current ORM user from the database."""
    unauthorized = HTTPException(
        status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise unauthorized from None
    user = session.get(User, int(claims.sub))
    if user is None:
        raise unauthorized
    return user


def require_role(role: AuthRole) -> Callable[..., Coroutine[Any, Any, User]]:
    """Contract: return ORM User for the requested role; otherwise HTTP 403."""

    async def dependency(
        user: Annotated[User, Depends(current_user)],
    ) -> User:
        if user.role != role:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return dependency
