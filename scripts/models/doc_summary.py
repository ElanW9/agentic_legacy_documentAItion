"""Structured summary of a documented package (future LLM structured output)."""

from typing import Literal

from pydantic import Field

from .common import StrictModel

UNKNOWN = "Unknown: needs human input"


class Citation(StrictModel):
    unit_id: str
    file: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class Claim(StrictModel):
    text: str
    citations: list[Citation] = Field(min_length=1)


class UnitSummary(StrictModel):
    unit_id: str
    purpose: Claim | Literal["Unknown: needs human input"]
    side_effects: list[Claim] = []
    tables_touched: list[str] = []
    risks: list[Claim] = []
    open_questions: list[str] = []


class PackageSummary(StrictModel):
    package: str
    purpose: Claim | Literal["Unknown: needs human input"]
    units: list[UnitSummary]
    open_questions: list[str] = []
