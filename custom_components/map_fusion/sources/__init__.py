"""Map source adapters. See base.py for what each provides."""
from __future__ import annotations

from types import ModuleType

from . import dreame, valetudo

ADAPTERS: dict[str, ModuleType] = {dreame.KIND: dreame, valetudo.KIND: valetudo}
