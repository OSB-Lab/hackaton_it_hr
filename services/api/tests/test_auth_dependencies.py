import asyncio
from typing import get_type_hints

import pytest

from app.models.user import User
from app.modules.auth.dependencies import current_user, require_role


def test_current_user_placeholder_cannot_authenticate():
    assert get_type_hints(current_user)["return"] is User
    with pytest.raises(NotImplementedError):
        asyncio.run(current_user())


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_role_placeholder_cannot_authorize(role):
    dependency = require_role(role)
    assert get_type_hints(dependency)["return"] is User
    user = User(
        id=1, email="demo@example.com", password_hash="fixture",
        role=role, is_verified=True,
    )
    with pytest.raises(NotImplementedError):
        asyncio.run(dependency(user))
