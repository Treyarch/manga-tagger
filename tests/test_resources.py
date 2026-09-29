from pathlib import Path

from manga_tagger.resources import ui_directory


def test_ui_directory_prefers_packaged_build(tmp_path: Path) -> None:
    module = tmp_path / "install" / "manga_tagger" / "resources.py"
    packaged = module.parent / "ui_dist"
    packaged.mkdir(parents=True)
    (packaged / "index.html").write_text("built", encoding="utf-8")

    assert ui_directory(module) == packaged


def test_ui_directory_falls_back_to_source_build(tmp_path: Path) -> None:
    module = tmp_path / "project" / "src" / "manga_tagger" / "resources.py"

    assert ui_directory(module) == tmp_path / "project" / "ui" / "dist"
