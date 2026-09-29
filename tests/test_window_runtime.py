"""Desktop runtime dependency checks that do not create a window."""

import sys

import pytest


@pytest.mark.skipif(sys.platform != "linux", reason="Linux GTK backend only")
def test_linux_gtk_runtime_is_importable() -> None:
    """The isolated app environment contains GTK and WebKitGTK bindings."""
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")

    from gi.repository import Gtk, WebKit2

    assert Gtk.get_major_version() == 3
    assert WebKit2.WebView is not None
