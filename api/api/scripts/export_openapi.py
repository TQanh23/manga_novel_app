"""Write the OpenAPI document without starting a server.

    uv run python -m api.scripts.export_openapi [path]

The Expo client is generated from this file (`npm run gen:api` in app/).
"""

import json
import sys
from pathlib import Path

from api.main import create_app


def main() -> None:
    document = json.dumps(create_app().openapi(), indent=2, ensure_ascii=False, sort_keys=True)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(document + "\n", encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(document + "\n")


if __name__ == "__main__":
    main()
