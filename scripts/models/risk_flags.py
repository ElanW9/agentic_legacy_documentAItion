"""Risky constructs found per unit."""

from enum import StrEnum

from .common import StrictModel


class RiskKind(StrEnum):
    DYNAMIC_SQL = "DYNAMIC_SQL"
    COMMIT = "COMMIT"
    ROLLBACK = "ROLLBACK"
    SAVEPOINT = "SAVEPOINT"  # SAVEPOINT or ROLLBACK TO SAVEPOINT
    AUTONOMOUS_TRANSACTION = "AUTONOMOUS_TRANSACTION"
    WHEN_OTHERS_SWALLOW = "WHEN_OTHERS_SWALLOW"  # handler without RAISE
    WHEN_OTHERS_HANDLED = "WHEN_OTHERS_HANDLED"  # handler that re-raises
    HARDCODED_VALUE = "HARDCODED_VALUE"
    PACKAGE_STATE = "PACKAGE_STATE"
    TRIGGER_DML = "TRIGGER_DML"
    NO_CALLER = "NO_CALLER"


class RiskFlag(StrictModel):
    unit_id: str
    kind: RiskKind
    file: str
    line: int
    snippet: str
    detail: str | None = None


class RiskFlags(StrictModel):
    parser_version: str
    flags: list[RiskFlag]
