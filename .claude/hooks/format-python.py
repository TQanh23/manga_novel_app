#!/usr/bin/env python3
"""PostToolUse: ruff-format a Python file after Claude edits it.

Keeps the `ruff format --check` step in CI from failing on formatting alone.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

raw = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
path = Path(raw)
if path.suffix != ".py" or not path.is_file():
    sys.exit(0)

subprocess.run(  # noqa: S603
    ["uv", "run", "--quiet", "ruff", "format", "--quiet", str(path)],  # noqa: S607
    cwd=os.environ.get("CLAUDE_PROJECT_DIR", "."),
    capture_output=True,
    check=False,
)
