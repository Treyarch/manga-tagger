"""Load config, bind the API, enqueue a startup scan, then open the window."""

import os
import sys
from pathlib import Path

from manga_tagger.api import create_app, enqueue_startup_scan, serve
from manga_tagger.config import ConfigError, app_paths, load_config
from manga_tagger.window import open_window


def main() -> None:
    """Start one desktop process. Invalid TOML exits 1 before the window opens."""
    paths = app_paths(sys.platform, dict(os.environ), Path.home())
    try:
        config = load_config(paths.config)
    except ConfigError as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(1) from exc
    ui_dir = Path(__file__).resolve().parents[2] / "ui" / "dist"
    app = create_app(config, paths.index, paths.thumbnails, ui_dir=ui_dir)
    port, close = serve(app)
    try:
        enqueue_startup_scan(app)
        open_window(f"http://127.0.0.1:{port}/")
    finally:
        app.state.box.runner.shutdown()
        close()


if __name__ == "__main__":
    main()
