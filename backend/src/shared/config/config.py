# SPDX-License-Identifier: Apache-2.0
"""Backward-compatibility facade — will be removed in Phase 6.

Existing code that imports ``backend_config`` or ``AppConfig`` continues to
work while consumers are migrated to ``LinkedOutSettings`` / ``get_config()``.
"""

from shared.config.settings import LinkedOutSettings, get_config

# Backward compatibility aliases
AppConfig = LinkedOutSettings
BaseConfig = LinkedOutSettings
backend_config = get_config()
