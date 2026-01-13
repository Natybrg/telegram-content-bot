"""
Configuration Module - DEPRECATED
This file is kept for backward compatibility only.
All configuration has been moved to core.config

Please update your imports:
    from config import *  →  from core import *
    import config  →  import core as config
"""
import warnings

# Show deprecation warning
warnings.warn(
    "Importing from 'config.py' is deprecated. "
    "Please use 'from core import *' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from core for backward compatibility
from core import *  # noqa: F401, F403

# For backward compatibility with ExecutorManager
from core.executor import ExecutorManager, executor_manager  # noqa: F401
