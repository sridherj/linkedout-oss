# SPDX-License-Identifier: Apache-2.0
"""Utilities module."""
from shared.utilities.correlation import (
    generate_correlation_id,
    get_correlation_id,
    set_correlation_id,
)
from shared.utilities.health_checks import (
    HealthCheckResult,
    check_api_keys,
    check_db_connection,
    check_disk_space,
    check_embedding_model,
    get_db_stats,
)
from shared.utilities.logger import get_logger, logger, set_level
from shared.utilities.metrics import read_summary, record_metric, update_summary
from shared.utilities.operation_report import (
    CoverageGap,
    OperationCounts,
    OperationFailure,
    OperationReport,
)
from shared.utilities.repair import (
    RepairDetection,
    RepairHook,
    clear_repair_hooks,
    get_repair_hooks,
    register_repair_hook,
)
from shared.utilities.setup_logger import get_setup_logger, setup_step

__all__ = [
    'CoverageGap',
    'HealthCheckResult',
    'OperationCounts',
    'OperationFailure',
    'OperationReport',
    'RepairDetection',
    'RepairHook',
    'check_api_keys',
    'check_db_connection',
    'check_disk_space',
    'check_embedding_model',
    'clear_repair_hooks',
    'generate_correlation_id',
    'get_correlation_id',
    'get_db_stats',
    'get_logger',
    'get_repair_hooks',
    'get_setup_logger',
    'logger',
    'read_summary',
    'record_metric',
    'register_repair_hook',
    'set_correlation_id',
    'set_level',
    'setup_step',
    'update_summary',
]

