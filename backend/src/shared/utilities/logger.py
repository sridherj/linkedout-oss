# SPDX-License-Identifier: Apache-2.0
"""Logging configuration and utilities — loguru-based.

Adapted from kraftx-aragent logger. Provides:
- Console + rotating file output with per-component routing
- Module-level log levels via LOG_LEVEL_<MODULE> env vars
- Stdlib logging intercept (so logging.getLogger() calls route through loguru)
- Automatic correlation ID injection from contextvars
"""
import logging
import os
import sys
from typing import Optional

from loguru import logger

from shared.config import get_config
from shared.utilities.correlation import get_correlation_id


class _StdlibIntercept(logging.Handler):
    """Route stdlib logging calls into loguru so all output goes through one pipeline."""

    def emit(self, record: logging.LogRecord) -> None:
        # Map stdlib level to loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Skip logging internals to reach the actual caller
        depth = 6
        logger.opt(depth=depth, exception=record.exc_info).bind(name=record.name).log(
            level, record.getMessage()
        )


# Components and their log files
COMPONENT_LOG_FILES = {
    'backend': 'backend.log',
    'cli': 'cli.log',
    'setup': 'setup.log',
    'enrichment': 'enrichment.log',
    'import': 'import.log',
    'queries': 'queries.log',
}


class LoggerSingleton:
    _instance = None
    _initialized = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if not LoggerSingleton._initialized:
            LoggerSingleton._initialized = True

            # Remove default loguru handler
            logger.remove()

            settings = get_config()
            self.default_log_level = settings.log_level
            self.module_log_levels: dict[str, str] = {}
            self._load_module_levels_from_env()

            # Log directory from config (defaults to ~/linkedout-data/logs)
            self.log_dir = settings.log_dir
            os.makedirs(self.log_dir, exist_ok=True)

            # Rotation policy from config (defaults: 50 MB / 30 days)
            rotation = settings.log_rotation
            retention = settings.log_retention

            # Configure patcher to inject correlation ID into every record
            logger.configure(patcher=self._patcher)

            # Console: compact, colorized — unchanged from original
            console_format = (
                '<green>{time:HH:mm:ss}</green> '
                '<level>{level.name[0]}</level> '
                '<cyan>{extra[module_compact]}</cyan> '
                '<level>{message}</level>'
            )
            self.console_handler = logger.add(
                sys.stderr,
                format=console_format,
                level='TRACE',
                filter=self._module_level_filter,
                enqueue=True,
                colorize=True,
                backtrace=True,
                diagnose=True,
            )

            # File format: verbose with full context + correlation ID
            file_format = (
                '{time:YYYY-MM-DD HH:mm:ss.SSS} '
                '| {level: <8} '
                '| {extra[module_full]}:{function}:{line} '
                '| {extra[correlation_id]} '
                '| {message}'
            )

            # Default file sink: backend.log (catches all logs)
            self.file_handler = logger.add(
                os.path.join(self.log_dir, 'backend.log'),
                format=file_format,
                level='TRACE',
                filter=self._module_level_filter,
                rotation=rotation,
                retention=retention,
                compression='gz',
                encoding='utf-8',
                enqueue=True,
                backtrace=True,
                diagnose=True,
            )

            # Per-component file sinks (exclude 'backend' — handled above)
            self._component_handlers: dict[str, int] = {}
            for component, filename in COMPONENT_LOG_FILES.items():
                if component == 'backend':
                    continue
                handler_id = logger.add(
                    os.path.join(self.log_dir, filename),
                    format=file_format,
                    level='TRACE',
                    filter=self._make_component_filter(component),
                    rotation=rotation,
                    retention=retention,
                    compression='gz',
                    encoding='utf-8',
                    enqueue=True,
                    backtrace=True,
                    diagnose=True,
                )
                self._component_handlers[component] = handler_id

            # Intercept stdlib logging → loguru
            logging.basicConfig(handlers=[_StdlibIntercept()], level=0, force=True)

        self.logger = logger

    @staticmethod
    def _patcher(record):
        """Inject correlation ID and ensure extras have defaults for formatting."""
        cid = get_correlation_id()
        record['extra'].setdefault('correlation_id', cid or '')
        record['extra'].setdefault('module_full', 'main')
        record['extra'].setdefault('module_compact', 'main')

    def _make_component_filter(self, component: str):
        """Create a filter function that passes only logs bound to a specific component.

        Args:
            component: The component name to filter for (e.g., 'cli', 'enrichment').

        Returns:
            A filter callable that also applies module-level filtering.
        """
        def _filter(record):
            if record.get('extra', {}).get('component') != component:
                return False
            return self._module_level_filter(record)
        return _filter

    def _load_module_levels_from_env(self):
        """Load LOG_LEVEL_<MODULE>=LEVEL from env. Underscores map to dots."""
        for key, value in os.environ.items():
            if key.startswith('LOG_LEVEL_') and key != 'LOG_LEVEL':
                module_name = key[10:].lower().replace('_', '.')
                if value.upper() in ('TRACE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
                    self.module_log_levels[module_name] = value.upper()

    def _shorten_module_name(self, module_name: str) -> str:
        if not module_name:
            return 'main'
        parts = module_name.split('.')
        if len(parts) <= 2:
            return module_name
        return f'{parts[1]}.{parts[-1]}'

    def _module_level_filter(self, record):
        module_name = record.get('extra', {}).get('name', record.get('name', ''))

        # Populate formatting extras
        record['extra']['module_full'] = module_name or 'main'
        record['extra']['module_compact'] = self._shorten_module_name(module_name)

        # Determine effective level for this module
        target_level = self.default_log_level
        if module_name in self.module_log_levels:
            target_level = self.module_log_levels[module_name]
        else:
            for prefix, level in self.module_log_levels.items():
                if module_name.startswith(prefix):
                    target_level = level
                    break

        return logger.level(record['level'].name).no >= logger.level(target_level).no

    def set_module_log_level(self, module_name: str, level: str):
        self.module_log_levels[module_name] = level.upper()

    def get_module_log_level(self, module_name: str) -> str:
        if module_name in self.module_log_levels:
            return self.module_log_levels[module_name]
        for prefix, level in self.module_log_levels.items():
            if module_name.startswith(prefix):
                return level
        return self.default_log_level


# ── Public API (backwards-compatible) ──────────────────────────────

def setup_logging(environment: str = 'local', log_level: str = 'INFO') -> None:
    """Initialize the logger singleton. Safe to call multiple times."""
    LoggerSingleton.get_instance()


def get_logger(
    name: Optional[str] = None,
    component: Optional[str] = None,
    operation: Optional[str] = None,
):
    """Return a loguru logger optionally bound with module name, component, and operation.

    Args:
        name: Module name for filtering (e.g., __name__).
        component: Subsystem name for per-component log file routing.
            Valid values: 'backend', 'cli', 'setup', 'enrichment', 'import', 'queries'.
        operation: Current operation name (e.g., 'import_csv', 'enrich_profile').

    Returns:
        A loguru logger instance, optionally bound with the provided context.
    """
    LoggerSingleton.get_instance()  # ensure initialized
    bindings = {}
    if name:
        bindings['name'] = name
    if component:
        bindings['component'] = component
    if operation:
        bindings['operation'] = operation
    return logger.bind(**bindings) if bindings else logger


def set_level(level: str) -> None:
    """Set the global default log level."""
    singleton = LoggerSingleton.get_instance()
    singleton.default_log_level = level.upper()


def set_module_log_level(module_name: str, level: str) -> None:
    LoggerSingleton.get_instance().set_module_log_level(module_name, level)


def get_module_log_level(module_name: str) -> str:
    return LoggerSingleton.get_instance().get_module_log_level(module_name)


# Default logger instance (used by db_session_manager etc.)
logger_instance = get_logger(__name__)
# Keep `logger` as an alias for backwards compatibility
logger = logger_instance
