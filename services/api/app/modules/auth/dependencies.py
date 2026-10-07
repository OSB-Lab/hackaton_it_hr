from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends

from app.models.user import User
from app.modules.auth.schemas import AuthRole


async def current_user() -> User:
    """Contract: validate Bearer JWT and return the authenticated ORM User."""
    raise NotImplementedError("Bearer JWT authentication is not implemented yet")


def require_role(role: AuthRole) -> Callable[..., Coroutine[Any, Any, User]]:
    """Contract: return ORM User for the requested role; otherwise HTTP 403."""

    async def dependency(
        user: Annotated[User, Depends(current_user)],
    ) -> User:
        # This placeholder must never grant access before RBAC is implemented.
        raise NotImplementedError("Role authorization is not implemented yet")

    return dependency
