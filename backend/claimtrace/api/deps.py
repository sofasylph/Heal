"""Request dependencies: database session and the calling actor."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from claimtrace.access import Actor, Role
from claimtrace.db.session import get_session

DB = Annotated[Session, Depends(get_session)]


def current_actor(
    x_user: Annotated[str | None, Header(max_length=100)] = None,
    x_role: Annotated[str | None, Header()] = None,
) -> Actor:
    """Demo identity from headers (no login yet). Defaults to a reviewer."""
    try:
        role = Role(x_role) if x_role else Role.REVIEWER
    except ValueError as e:
        raise HTTPException(400, f"Unknown role '{x_role}'") from e
    user = (x_user or "demo.reviewer").strip() or "demo.reviewer"
    return Actor(user=user, role=role)


CurrentActor = Annotated[Actor, Depends(current_actor)]
