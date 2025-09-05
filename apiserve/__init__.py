# Makes apiserve a package

__all__ = [
    "create_app",
]

from .main import create_app  # noqa: E402,F401


