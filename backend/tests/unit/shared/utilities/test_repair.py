# SPDX-License-Identifier: Apache-2.0
"""Tests for the auto-repair hook framework."""
from __future__ import annotations

from shared.utilities.operation_report import OperationReport, OperationCounts
from shared.utilities.repair import (
    RepairDetection,
    RepairHook,
    clear_repair_hooks,
    get_repair_hooks,
    register_repair_hook,
)


class TestRepairDetection:
    """Tests for the RepairDetection dataclass."""

    def test_defaults(self):
        """Default values: not needing repair, count 0, empty description."""
        detection = RepairDetection(needs_repair=False)
        assert detection.needs_repair is False
        assert detection.count == 0
        assert detection.description == ''

    def test_all_fields(self):
        """All fields are set correctly."""
        detection = RepairDetection(
            needs_repair=True, count=42, description='42 items need fixing',
        )
        assert detection.needs_repair is True
        assert detection.count == 42
        assert detection.description == '42 items need fixing'


class TestRepairHook:
    """Tests for the RepairHook dataclass."""

    def test_fields_stored(self):
        """Hook stores name, description, detect, and repair callables."""
        detect_fn = lambda: RepairDetection(needs_repair=False)
        repair_fn = lambda: OperationReport(operation='test')

        hook = RepairHook(
            name='test_hook',
            description='A test hook',
            detect=detect_fn,
            repair=repair_fn,
        )
        assert hook.name == 'test_hook'
        assert hook.description == 'A test hook'
        assert hook.detect is detect_fn
        assert hook.repair is repair_fn


class TestRepairRegistry:
    """Tests for register_repair_hook() and get_repair_hooks()."""

    def setup_method(self):
        """Clear the registry before each test."""
        clear_repair_hooks()

    def teardown_method(self):
        """Clear the registry after each test."""
        clear_repair_hooks()

    def test_register_adds_hook(self):
        """register_repair_hook() adds a hook to the registry."""
        hook = RepairHook(
            name='test',
            description='Test hook',
            detect=lambda: RepairDetection(needs_repair=False),
            repair=lambda: OperationReport(operation='test'),
        )
        register_repair_hook(hook)
        hooks = get_repair_hooks()
        assert len(hooks) == 1
        assert hooks[0].name == 'test'

    def test_get_returns_copy(self):
        """get_repair_hooks() returns a defensive copy."""
        hook = RepairHook(
            name='test',
            description='Test hook',
            detect=lambda: RepairDetection(needs_repair=False),
            repair=lambda: OperationReport(operation='test'),
        )
        register_repair_hook(hook)

        hooks1 = get_repair_hooks()
        hooks2 = get_repair_hooks()
        assert hooks1 is not hooks2
        assert len(hooks1) == len(hooks2) == 1

    def test_register_multiple_hooks(self):
        """Multiple hooks can be registered."""
        for i in range(3):
            register_repair_hook(RepairHook(
                name=f'hook_{i}',
                description=f'Hook {i}',
                detect=lambda: RepairDetection(needs_repair=False),
                repair=lambda: OperationReport(operation='test'),
            ))
        assert len(get_repair_hooks()) == 3

    def test_duplicate_name_replaces(self):
        """Registering a hook with the same name replaces the existing one."""
        hook_v1 = RepairHook(
            name='test',
            description='Version 1',
            detect=lambda: RepairDetection(needs_repair=False),
            repair=lambda: OperationReport(operation='v1'),
        )
        hook_v2 = RepairHook(
            name='test',
            description='Version 2',
            detect=lambda: RepairDetection(needs_repair=True, count=5),
            repair=lambda: OperationReport(operation='v2'),
        )

        register_repair_hook(hook_v1)
        register_repair_hook(hook_v2)

        hooks = get_repair_hooks()
        assert len(hooks) == 1
        assert hooks[0].description == 'Version 2'

    def test_clear_removes_all(self):
        """clear_repair_hooks() empties the registry."""
        register_repair_hook(RepairHook(
            name='test',
            description='Test',
            detect=lambda: RepairDetection(needs_repair=False),
            repair=lambda: OperationReport(operation='test'),
        ))
        assert len(get_repair_hooks()) == 1

        clear_repair_hooks()
        assert len(get_repair_hooks()) == 0


class TestRepairDetectFunction:
    """Tests for detect functions returning RepairDetection."""

    def test_detect_returns_repair_detection(self):
        """Detect callable returns a RepairDetection with correct fields."""
        def detect_fn():
            return RepairDetection(needs_repair=True, count=10, description='10 items')

        detection = detect_fn()
        assert isinstance(detection, RepairDetection)
        assert detection.needs_repair is True
        assert detection.count == 10

    def test_repair_returns_operation_report(self):
        """Repair callable returns an OperationReport."""
        def repair_fn():
            return OperationReport(
                operation='test-repair',
                counts=OperationCounts(total=10, succeeded=8, skipped=1, failed=1),
            )

        report = repair_fn()
        assert isinstance(report, OperationReport)
        assert report.operation == 'test-repair'
        assert report.counts.succeeded == 8


class TestRepairFlow:
    """Tests for the detect → repair flow ordering."""

    def setup_method(self):
        clear_repair_hooks()

    def teardown_method(self):
        clear_repair_hooks()

    def test_detect_then_repair_order(self):
        """Hooks are called detect → repair in sequence."""
        call_order = []

        def detect():
            call_order.append('detect')
            return RepairDetection(needs_repair=True, count=1, description='1 item')

        def repair():
            call_order.append('repair')
            return OperationReport(operation='test')

        hook = RepairHook(
            name='ordered_test',
            description='Order test',
            detect=detect,
            repair=repair,
        )
        register_repair_hook(hook)

        hooks = get_repair_hooks()
        for h in hooks:
            detection = h.detect()
            if detection.needs_repair:
                h.repair()

        assert call_order == ['detect', 'repair']

    def test_repair_not_called_when_not_needed(self):
        """Repair is not called when detect says no repair needed."""
        call_order = []

        def detect():
            call_order.append('detect')
            return RepairDetection(needs_repair=False)

        def repair():
            call_order.append('repair')
            return OperationReport(operation='test')

        hook = RepairHook(
            name='no_repair_test',
            description='No repair needed',
            detect=detect,
            repair=repair,
        )
        register_repair_hook(hook)

        hooks = get_repair_hooks()
        for h in hooks:
            detection = h.detect()
            if detection.needs_repair:
                h.repair()

        assert call_order == ['detect']
