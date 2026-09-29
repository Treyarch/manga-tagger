"""Locate application resources without importing the desktop window."""

from pathlib import Path


def ui_directory(package_file: Path | None = None) -> Path:
    """Return the compiled UI directory for an install or source checkout.

    Wheels embed Vite's output beside the Python package. Editable installs use
    the repository's ``ui/dist`` directory so rebuilding the client remains a
    normal frontend development step.
    """
    module_file = Path(__file__) if package_file is None else Path(package_file)
    packaged = module_file.resolve().parent / "ui_dist"
    if (packaged / "index.html").is_file():
        return packaged
    return module_file.resolve().parents[2] / "ui" / "dist"
