import argparse
import json
from pathlib import Path

from gui.api.app import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the ReliFinder GUI OpenAPI document")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
