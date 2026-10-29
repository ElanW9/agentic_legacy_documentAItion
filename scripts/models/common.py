"""Base model, enums and source references shared by all schemas."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base for every model: unknown fields are an error, not silently dropped."""

    model_config = ConfigDict(extra="forbid")


class ObjectType(StrEnum):
    PACKAGE = "PACKAGE"
    PROCEDURE = "PROCEDURE"
    FUNCTION = "FUNCTION"
    TABLE = "TABLE"
    VIEW = "VIEW"
    TRIGGER = "TRIGGER"
    SEQUENCE = "SEQUENCE"
    EXTERNAL = "EXTERNAL"  # Oracle-supplied, e.g. DBMS_OUTPUT


class Visibility(StrEnum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"


class ParamMode(StrEnum):
    IN = "IN"
    OUT = "OUT"
    IN_OUT = "IN OUT"


class SourceRef(StrictModel):
    """A line range in a source file. Lines are 1-based and inclusive."""

    file: str = Field(description="Path relative to the repo root, forward slashes.")
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @model_validator(mode="after")
    def _check_order(self) -> "SourceRef":
        if self.end_line < self.start_line:
            raise ValueError(f"end_line {self.end_line} < start_line {self.start_line}")
        return self
