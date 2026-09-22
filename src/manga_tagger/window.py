"""The desktop window. This is the only module that imports pywebview."""

import json
import time
import urllib.parse

import webview
from webview.dom import DOMEventHandler, _dnd_state


def destroy_window() -> None:
    """Close the Manga Tagger window. No-op when no window is open."""
    if webview.windows:
        webview.windows[0].destroy()


def pick_folder() -> str | None:
    """Open the native folder dialog on the current window.

    Returns:
        The chosen directory, or ``None`` when the dialog is cancelled or
        no window is open.
    """
    if not webview.windows:
        return None
    chosen = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
    if not chosen:
        return None
    return chosen[0]


def open_window(url: str) -> None:
    """Open the Manga Tagger window on the API origin and block until it closes.

    Args:
        url: ``http://127.0.0.1:{port}/``. The client does not call into Python.
            A drop on ``#places`` dispatches ``folders-dropped``.
    """
    window = webview.create_window("Manga Tagger", url, width=1280, height=800)
    window.events.loaded += lambda: _bind_folder_drop(window)
    webview.start()


def _bind_folder_drop(window: webview.Window) -> None:
    """Listen for a native drop on the places sidebar once it exists."""
    if getattr(window, "_folder_drop_bound", False):
        return
    places = None
    for _ in range(40):
        places = window.dom.get_element("#places")
        if places is not None:
            break
        time.sleep(0.05)
    if places is None:
        return

    def on_drop(event: object) -> None:
        _dispatch_dropped(window, _drop_paths(event))

    places.on("drop", DOMEventHandler(on_drop, prevent_default=True))
    window._folder_drop_bound = True  # type: ignore[attr-defined]


def _drop_paths(event: object) -> list[str]:
    """Absolute paths from one drop. Files and folders both come through."""
    paths: list[str] = []
    seen: set[str] = set()
    transfer = event.get("dataTransfer") if isinstance(event, dict) else None
    files = transfer.get("files", []) if isinstance(transfer, dict) else []
    if isinstance(files, list):
        for file in files:
            if not isinstance(file, dict):
                continue
            full = file.get("pywebviewFullPath")
            if isinstance(full, str):
                _keep_path(paths, seen, full)
    for _name, raw in list(_dnd_state["paths"]):
        _keep_path(paths, seen, str(raw))
    _dnd_state["paths"].clear()
    return paths


def _keep_path(paths: list[str], seen: set[str], raw: str) -> None:
    text = urllib.parse.unquote(raw.strip())
    if text.startswith("file://"):
        text = urllib.parse.unquote(text.removeprefix("file://"))
    if text == "" or text in seen:
        return
    seen.add(text)
    paths.append(text)


def _dispatch_dropped(window: webview.Window, paths: list[str]) -> None:
    literal = json.dumps(json.dumps({"paths": paths}))
    window.evaluate_js(
        "window.dispatchEvent(new CustomEvent('folders-dropped', "
        f"{{ detail: JSON.parse({literal}) }}))"
    )
