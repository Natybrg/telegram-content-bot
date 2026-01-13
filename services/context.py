"""
Application Context Service - DEPRECATED
This file has been moved to core.context

Please update your imports:
    from services.context import *  →  from core.context import *
    from services.context import AppContext  →  from core import AppContext
"""
import warnings

# Show deprecation warning
warnings.warn(
    "Importing from 'services.context' is deprecated. "
    "Please use 'from core.context import *' or 'from core import AppContext, get_context' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from core.context for backward compatibility
from core.context import *  # noqa: F401, F403
