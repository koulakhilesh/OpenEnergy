"""Web app: value a battery on historic GB prices or on a NESO FES pathway's modelled prices.

A FastAPI JSON API (``/api``) and the React front end built from ``web/`` (served from
``$OPENENERGY_WEB`` or ``./web/dist``). Run locally with ``uv run uvicorn openenergy.app:app``
after ``npm --prefix web run build``; Vercel serves ``app.py`` at the repository root. Data
are read from ``$OPENENERGY_DATA`` or ``./data``.
"""

from openenergy.app.server import app

__all__ = ["app"]
