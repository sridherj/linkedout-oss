# SPDX-License-Identifier: Apache-2.0
"""Custom pydantic-settings v2 sources for YAML config and secrets files."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic.fields import FieldInfo
from pydantic_settings import PydanticBaseSettingsSource

_DEFAULT_DATA_DIR = '~/linkedout-data'


def _resolve_data_dir() -> Path:
    raw = os.environ.get('LINKEDOUT_DATA_DIR', _DEFAULT_DATA_DIR)
    return Path(os.path.expanduser(raw))


class YamlConfigSource(PydanticBaseSettingsSource):
    """Reads settings from ``{data_dir}/config/config.yaml``."""

    def __init__(self, settings_cls: type) -> None:
        super().__init__(settings_cls)
        self._path = _resolve_data_dir() / 'config' / 'config.yaml'
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        with open(self._path) as f:
            return yaml.safe_load(f) or {}

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        val = self._data.get(field_name)
        return val, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._data


class YamlSecretsSource(PydanticBaseSettingsSource):
    """Reads settings from ``{data_dir}/config/secrets.yaml``.

    On Unix, warns to stderr if the file permissions are not ``0600``.
    """

    def __init__(self, settings_cls: type) -> None:
        super().__init__(settings_cls)
        self._path = _resolve_data_dir() / 'config' / 'secrets.yaml'
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        self._check_permissions()
        with open(self._path) as f:
            return yaml.safe_load(f) or {}

    def _check_permissions(self) -> None:
        if os.name == 'nt':
            return
        mode = self._path.stat().st_mode & 0o777
        if mode != 0o600:
            print(
                f'WARNING: {self._path} has permissions {oct(mode)}; '
                f'recommended 0600. Fix with: chmod 600 {self._path}',
                file=sys.stderr,
            )

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        val = self._data.get(field_name)
        return val, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._data
