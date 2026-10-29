"""Documentation status per package (state/doc-status.json)."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from .common import StrictModel


class DocState(StrEnum):
    TODO = "todo"
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    STALE = "stale"  # source hash changed since the doc was written


class DocStatusEntry(StrictModel):
    package: str
    doc_path: str
    source_files: list[str]
    source_hash: str = Field(description="sha256 over the source files, in listed order.")
    status: DocState
    updated_at: datetime
    validation_passed: bool | None = None


class DocStatusFile(StrictModel):
    entries: dict[str, DocStatusEntry] = {}
