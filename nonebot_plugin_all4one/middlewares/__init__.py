import importlib
from pathlib import Path
from typing import Optional, cast

from nonebot.log import logger

from .base import Queue, Middleware

MIDDLEWARE_MAP = {}
for file in Path(__file__).parent.rglob("*.py"):
    if file.name == "base.py" or file.name.startswith("_"):
        continue
    rel_path = file.resolve().relative_to(Path(__file__).parent.resolve())
    module_name = ".".join(
        ("nonebot_plugin_all4one", "middlewares")
        + rel_path.parts[:-1]
        + (rel_path.stem,)
    )
    try:
        module = importlib.import_module(module_name)
        if middleware := cast(
            Optional[Middleware], getattr(module, "Middleware", None)
        ):
            MIDDLEWARE_MAP[middleware.get_name()] = middleware
    except Exception:
        logger.warning(f"Failed to import {module_name}")
