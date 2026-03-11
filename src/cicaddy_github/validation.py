"""Input validation utilities for git references and numeric parameters."""

import re

# Git ref names: alphanumeric, dots, hyphens, underscores, slashes
_SAFE_GIT_REF = re.compile(r"^[a-zA-Z0-9._/\-]+$")


def validate_git_ref(ref: str, name: str = "ref") -> None:
    """Validate a git ref name to prevent command injection."""
    if not ref or not _SAFE_GIT_REF.match(ref):
        raise ValueError(f"Invalid git {name}: {ref!r}")


def validate_positive_int(value: int, name: str = "value") -> None:
    """Validate that a value is a positive integer."""
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")
