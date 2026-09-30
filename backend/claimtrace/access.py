"""Roles and permissions.

v0.3 has no login: the caller states who they are (X-User / X-Role headers, set by the
UI's role switcher). The permission model is real and enforced server-side, so adding
authentication later only changes where the Actor comes from.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Role(StrEnum):
    REVIEWER = "reviewer"
    SENIOR_REVIEWER = "senior_reviewer"
    AUDITOR = "auditor"


class Permission(StrEnum):
    CREATE_CLAIM = "claims:create"
    ADJUDICATE = "claims:adjudicate"
    DECIDE = "claims:decide"
    DECIDE_ESCALATED = "claims:decide_escalated"
    UPDATE_SETTINGS = "settings:update"


GRANTS: dict[Role, set[Permission]] = {
    Role.REVIEWER: {Permission.CREATE_CLAIM, Permission.ADJUDICATE, Permission.DECIDE},
    Role.SENIOR_REVIEWER: set(Permission),
    Role.AUDITOR: set(),  # read-only: queue, claims, audit trails, analytics
}


class Actor(BaseModel):
    user: str
    role: Role

    def can(self, permission: Permission) -> bool:
        return permission in GRANTS[self.role]

    @property
    def label(self) -> str:
        return f"{self.role.value}:{self.user}"


class AccessDenied(Exception):
    pass


def require(actor: Actor, permission: Permission, why: str = "") -> None:
    if not actor.can(permission):
        raise AccessDenied(why or f"Role '{actor.role.value}' may not {permission.value}")


SYSTEM_ACTOR = Actor(user="claimtrace", role=Role.SENIOR_REVIEWER)
