"""Vercel entrypoint: serves the OpenEnergy web app (``openenergy.app``)."""

from openenergy.app import app

__all__ = ["app"]
