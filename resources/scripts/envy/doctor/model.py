"""Shared result model for doctor checks."""

from dataclasses import dataclass, field
from typing import Any, Literal

Status = Literal["ok", "warn", "error", "info"]


@dataclass
class CheckResult:
    section: str
    name: str
    status: Status
    message: str
    hint: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return self.status == "error"

    @property
    def warned(self) -> bool:
        return self.status == "warn"


def ok(section: str, name: str, message: str, **details: Any) -> CheckResult:
    return CheckResult(section=section, name=name, status="ok", message=message, details=details)


def warn(section: str, name: str, message: str, hint: str = "", **details: Any) -> CheckResult:
    return CheckResult(section=section, name=name, status="warn", message=message, hint=hint, details=details)


def error(section: str, name: str, message: str, hint: str = "", **details: Any) -> CheckResult:
    return CheckResult(section=section, name=name, status="error", message=message, hint=hint, details=details)


def info(section: str, name: str, message: str, hint: str = "", **details: Any) -> CheckResult:
    return CheckResult(section=section, name=name, status="info", message=message, hint=hint, details=details)
