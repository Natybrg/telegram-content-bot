"""
Settings Plugin Package
Modular settings management system

This package contains:
- menu.py: Main settings menu and navigation
- templates.py: Template viewing and editing
- channels.py: Channel/group management
- cookies.py: YouTube cookies management
- callbacks.py: Shared callback utilities

All handlers are automatically registered when this package is imported.
"""

import logging

# Import all modules to register their handlers
from . import menu
from . import templates
from . import channels
from . import cookies
from . import callbacks

logger = logging.getLogger(__name__)

# Export commonly used items if needed
__all__ = [
    'menu',
    'templates',
    'channels',
    'cookies',
    'callbacks'
]

__version__ = "2.0.0"

logger.info("✅ Settings plugin package loaded - all handlers registered")
