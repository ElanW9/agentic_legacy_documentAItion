"""Export the JSON Schema of each top-level model to schemas/.

Usage:
    python -m scripts.export_schemas
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.models import SCHEMA_ROOTS  # noqa: E402


def main() -> int:
    out_dir = REPO_ROOT / "schemas"
    out_dir.mkdir(exist_ok=True)
    for name, model in SCHEMA_ROOTS.items():
        path = out_dir / f"{name}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
