# SPDX-License-Identifier: Apache-2.0
"""Auto-repair hook framework for LinkedOut diagnostics.

Provides an extensible registry of repair hooks that detect and fix
common data issues. Each hook has a ``detect`` function (returns what
needs fixing) and a ``repair`` function (performs the fix and returns
an ``OperationReport``).

Usage::

    from shared.utilities.repair import (
        RepairDetection,
        RepairHook,
        get_repair_hooks,
        register_repair_hook,
    )

    hook = RepairHook(
        name="missing_embeddings",
        description="Profiles without embeddings",
        detect=lambda: RepairDetection(needs_repair=True, count=42, description="42 profiles missing embeddings"),
        repair=lambda: some_operation_report,
    )
    register_repair_hook(hook)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from shared.utilities.operation_report import OperationReport


@dataclass
class RepairDetection:
    """Result of a repair hook's detection phase.

    Attributes:
        needs_repair: Whether any items need repair.
        count: Number of items that need repair.
        description: Human-readable description of the issue.
    """

    needs_repair: bool
    count: int = 0
    description: str = ''


@dataclass
class RepairHook:
    """A registered repair hook with detect and repair callables.

    Attributes:
        name: Short identifier (e.g., ``"missing_embeddings"``).
        description: Human-readable description of what this hook checks.
        detect: Callable that returns a ``RepairDetection`` describing
            whether repair is needed and how many items are affected.
        repair: Callable that performs the repair and returns an
            ``OperationReport`` describing the result.
    """

    name: str
    description: str
    detect: Callable[[], RepairDetection]
    repair: Callable[[], OperationReport]


_repair_hooks: list[RepairHook] = []


def register_repair_hook(hook: RepairHook) -> None:
    """Register a new repair hook.

    Other phases call this to add their own hooks. Duplicate names are
    silently replaced.
    """
    # Replace existing hook with same name
    for i, existing in enumerate(_repair_hooks):
        if existing.name == hook.name:
            _repair_hooks[i] = hook
            return
    _repair_hooks.append(hook)


def get_repair_hooks() -> list[RepairHook]:
    """Return all registered repair hooks (defensive copy)."""
    return list(_repair_hooks)


def clear_repair_hooks() -> None:
    """Remove all registered hooks. Primarily for testing."""
    _repair_hooks.clear()
