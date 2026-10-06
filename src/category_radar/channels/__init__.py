"""Channel adapters. Importing this package registers all built-in adapters."""
from . import alza, arukereso, ceneo, geizhals, mediamarkt, otto, toppreise  # noqa: F401
from .base import ChannelAdapter, available_adapters, get_adapter

__all__ = ["ChannelAdapter", "available_adapters", "get_adapter"]
