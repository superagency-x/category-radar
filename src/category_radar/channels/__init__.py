"""Channel adapters. Importing this package registers all built-in adapters."""

from . import (  # noqa: F401
    alza,
    arukereso,
    ceneo,
    geizhals,
    mediamarkt,
    otto,
    toppreise,
)
from .base import ChannelAdapter, available_adapters, get_adapter

__all__ = ["ChannelAdapter", "available_adapters", "get_adapter"]
