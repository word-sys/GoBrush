from __future__ import annotations
import sys
from gobrush.app import GoBrushApp


def main() -> int:
    app = GoBrushApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
