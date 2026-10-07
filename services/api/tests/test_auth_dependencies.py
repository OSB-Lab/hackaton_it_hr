import asyncio
from typing import get_type_hints

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.modules.auth.dependencies import current_user, require_role


def test_current_user_returns_orm_type():
    assert get_type_hints(current_user)["return"] is User


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_role_returns_same_orm_user(role):
    dependency = require_role(role)
    assert get_type_hints(dependency)["return"] is User
    user = User(
        id=1, email="demo@example.com", password_hash="fixture",
        role=role, is_verified=True,
    )
    assert asyncio.run(dependency(user)) is user
    user.role = "employer" if role == "candidate" else "candidate"
    with pytest.raises(HTTPException) as error:
        asyncio.run(dependency(user))
    assert error.value.status_code == 403
