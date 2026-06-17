from __future__ import annotations

from importlib import import_module

from .base import LabelPipeline

__all__ = ["LabelPipeline", "load_module_class", "resolve_module_name"]


def resolve_module_name(name: str) -> str:
    if not name or not name.strip():
        raise ValueError("module name must not be empty")
    return f"labelohlcv.modules.{name.strip()}"


def load_module_class(name: str) -> type[LabelPipeline]:
    module = import_module(resolve_module_name(name))
    module_class = getattr(module, "Module", None)
    if module_class is None:
        raise AttributeError(f"Module labelohlcv.modules.{name} must define class Module")
    if not issubclass(module_class, LabelPipeline):
        raise TypeError(f"labelohlcv.modules.{name}.Module must inherit from LabelPipeline")
    return module_class
