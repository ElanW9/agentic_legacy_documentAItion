"""Shared Pydantic models for extracted metadata, doc status and doc summaries."""

from .common import ObjectType, ParamMode, SourceRef, StrictModel, Visibility
from .dependencies import Dependency, DependencyGraph, DependencyKind
from .doc_status import DocState, DocStatusEntry, DocStatusFile
from .doc_summary import UNKNOWN, Citation, Claim, PackageSummary, UnitSummary
from .objects import (
    Column,
    Constraint,
    ConstraintKind,
    ObjectCatalog,
    Package,
    PackageVariable,
    Parameter,
    Sequence,
    SourceFile,
    Subprogram,
    Table,
    Trigger,
    View,
)
from .risk_flags import RiskFlag, RiskFlags, RiskKind
from .table_usage import AccessVia, Operation, TableAccess, TableUsage

# Top-level documents exported to schemas/ as JSON Schema.
SCHEMA_ROOTS = {
    "objects": ObjectCatalog,
    "dependencies": DependencyGraph,
    "table_usage": TableUsage,
    "risk_flags": RiskFlags,
    "doc_status": DocStatusFile,
    "package_summary": PackageSummary,
}
