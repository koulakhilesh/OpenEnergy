"""Write the web app's OpenAPI schema, which the front end's TypeScript types come from.

Run: uv run python scripts/export_openapi.py && npm --prefix web run api-types
"""

import json
from pathlib import Path

from openenergy.app import app

OUT = Path(__file__).parents[1] / "web/src/api/openapi.json"


def schema() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(schema())
    print(f"wrote {OUT}")
