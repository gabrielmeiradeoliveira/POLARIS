"""Compatibility namespace for legacy deicide imports."""

import polaris as _polaris
from polaris import __version__

__path__ = _polaris.__path__
__all__ = ["__version__"]
