"""Shared Jinja2 environment."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from myparcel.config import settings

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")
templates.env.globals["settings"] = settings
