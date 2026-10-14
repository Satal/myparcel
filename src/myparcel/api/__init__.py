"""API routes package."""

from myparcel.api.auth import router as auth_router
from myparcel.api.routes import router

__all__ = ["auth_router", "router"]
