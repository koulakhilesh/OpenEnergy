"""Web app: value a battery on historic GB prices or on a NESO FES pathway's modelled prices.

Run locally with ``uv run uvicorn openenergy.app:app``; Vercel serves ``app.py`` at the
repository root. Data are read from ``$OPENENERGY_DATA`` or ``./data``.
"""

from openenergy.app.server import app

__all__ = ["app"]
