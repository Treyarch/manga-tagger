"""The desktop window. This is the only module that imports pywebview."""

import webview


def open_window(url: str) -> None:
    """Open the Manga Tagger window on the API origin and block until it closes.

    Args:
        url: ``http://127.0.0.1:{port}/``. There is no JavaScript bridge.
    """
    webview.create_window("Manga Tagger", url, width=1280, height=800)
    webview.start()
