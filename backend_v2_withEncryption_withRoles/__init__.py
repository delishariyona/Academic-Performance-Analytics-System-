"""Package marker for backend_v2_withEncryption_withRoles.

This file makes the directory importable as a package for tests that
use `from backend_v2_withEncryption_withRoles import ...`.

Expose the Flask `app` object at package level so tests can do
`from backend_v2_withEncryption_withRoles import app` and call
`app.test_client()`.
"""

# Import the Flask app object into package namespace
from .app import app as app

# Re-export commonly used modules
from . import config, crypto, email_service, ml_engine, models

__all__ = [
    "app",
    "config",
    "crypto",
    "email_service",
    "ml_engine",
    "models",
]
