"""Places, selection, forms, jobs, and save/rename/convert bodies."""

from pathlib import Path

import httpx
import pytest

from manga_tagger.archives.errors import BatchFieldError
from manga_tagger.archives.rename import OFFERED_RENAME_TEMPLATE
from manga_tagger.archives.results import FileResult
from manga_tagger.index import LibraryIndexError, ScanResult, Volume
from manga_tagger.jobs import JobBusyError, JobCancelled, JobRunner
from manga_tagger.providers import parse_number
from manga_tagger.shell import (
    FORM_FIELDS,
    SHARED_FIELDS,
    accept_root_paths,
    default_client,
    edit_field,
    form_from_volumes,
    merge_load_patch,
    places_from_volumes,
    preferred_load_number,
    preview_rename,
    run_convert,
    run_list_issues,
    run_load,
    run_rename,
    run_save,
    run_scan,
    run_search,
    select_plain,
    select_range,
    select_toggle,
    selection_after_filter,
    volumes_for_roots,
    volumes_for_shelf,
    volumes_in_place,
)


def test_imports_do_not_load_webview() -> None:
    import sys

    import manga_tagger.api
    import manga_tagger.config
    import manga_tagger.jobs
    import manga_tagger.shell

    assert manga_tagger.api and manga_tagger.config
    assert "webview" not in sys.modules


def test_accept_root_paths_keeps_a_directory(tmp_path: Path) -> None:
    folder = tmp_path / "Claymore"
    folder.mkdir()
    note = tmp_path / "note.txt"
    note.write_text("x", encoding="utf-8")
    current = "/already"
    roots, added = accept_root_paths(
        [current],
        [str(folder), str(note), "relative", str(folder), 3],
    )
    resolved = str(folder.resolve())
    assert added == [resolved]
    assert roots == [current, resolved]
    again, extra = accept_root_paths(roots, [str(folder)])
    assert extra == []
    assert again == roots


def test_places_and_selection() -> None:
    claymore_a = _volume("/books/Claymore/a.cbz", series="Claymore")
    claymore_b = _volume("/books/Claymore/b.cbz", status="failed")
    other = _volume("/books/Other/Claymore/c.cbz", series="Other")
    nested = _volume("/books/Claymore/extra/v01.cbz")
    rooted = _volume("/books/root.cbz")
    rows = [claymore_a, claymore_b, other, nested, rooted]
    places = places_from_volumes(rows)
    labels = {place.path: place.label for place in places}
    assert labels["/books/Claymore"] == "books / Claymore"
    assert labels["/books/Other/Claymore"] == "Other / Claymore"
    assert labels["/books/Claymore/extra"] == "extra"
    assert "/books" in labels
    assert [place.path for place in places] == sorted(labels)
    in_claymore = volumes_in_place(rows, "/books/Claymore")
    assert [row.path for row in in_claymore] == [
        "/books/Claymore/a.cbz",
        "/books/Claymore/b.cbz",
    ]
    all_shelf = volumes_for_shelf(rows, None)
    assert [row.name for row in all_shelf] == sorted(row.name for row in rows)
    assert volumes_for_shelf(rows, "/books/Claymore") == in_claymore
    extra_only = [nested]
    assert places_from_volumes(extra_only)[0].path == "/books/Claymore/extra"
    assert volumes_in_place(extra_only, "/books/Claymore") == []
    direct = [_volume("/books/only.cbz")]
    assert places_from_volumes(direct)[0].path == "/books"

    kept = volumes_for_roots(rows, ["/books"])
    assert kept == rows
    outside = volumes_for_roots([_volume("/books-extra/a.cbz")], ["/books"])
    assert outside == []
    original = [claymore_a]
    assert volumes_for_roots(original, []) == []
    assert original == [claymore_a]

    visible = ["a", "b", "c"]
    selection = select_plain(visible, "a")
    selection = select_toggle(visible, selection, "b")
    hidden = selection_after_filter(["b", "c"], selection)
    assert hidden.paths == ("b",)
    assert hidden.anchor == "b"


def test_selection_transitions() -> None:
    visible = ["a", "b", "c", "d"]
    plain = select_plain(visible, "b")
    assert plain.paths == ("b",) and plain.anchor == "b"
    ranged = select_range(visible, plain, "d")
    assert ranged.paths == ("b", "c", "d") and ranged.anchor == "b"
    backward = select_range(visible, plain, "a")
    assert backward.paths == ("a", "b") and backward.anchor == "b"
    assert select_range(visible, select_plain(visible, "z"), "a").paths == ("a",)
    empty = select_toggle(visible, select_plain(visible, "a"), "a")
    assert empty.paths == () and empty.anchor is None
    first = select_toggle(visible, empty, "c")
    assert first.paths == ("c",) and first.anchor == "c"
    added = select_toggle(visible, first, "a")
    assert added.paths == ("a", "c") and added.anchor == "c"


def test_form_and_merge() -> None:
    one = form_from_volumes([_volume("/books/a.cbz", number="4", series="Claymore")])
    assert one is not None
    assert one["mode"] == "one"
    assert list(one["values"]) == list(FORM_FIELDS)
    assert one["values"]["Number"] == {"value": "4", "dirty": False}
    assert one["values"]["PageCount"] == {"value": "1", "dirty": False}
    assert "Pages" not in one["values"]

    blank_pages = form_from_volumes(
        [
            _volume(
                "/books/a.cbz",
                number="4",
                page_count="",
                archive_page_count=42,
            )
        ]
    )
    assert blank_pages is not None
    assert blank_pages["values"]["PageCount"] == {"value": "42", "dirty": False}

    kept = form_from_volumes(
        [
            _volume(
                "/books/a.cbz",
                page_count="10",
                archive_page_count=42,
            )
        ]
    )
    assert kept is not None
    assert kept["values"]["PageCount"] == {"value": "10", "dirty": False}

    no_archive = form_from_volumes(
        [_volume("/books/a.cbz", page_count="", archive_page_count=None)]
    )
    assert no_archive is not None
    assert no_archive["values"]["PageCount"] == {"value": "", "dirty": False}

    edited = edit_field(one, "Number", "9")
    assert edited["values"]["Number"] == {"value": "9", "dirty": True}

    shared = form_from_volumes(
        [
            _volume(
                "/books/a.cbz", series="Claymore", publisher="Shueisha", manga="No"
            ),
            _volume("/books/b.cbz", series="Monster", publisher="Shueisha", manga="No"),
        ]
    )
    assert shared is not None
    assert shared["mode"] == "many"
    assert list(shared["values"]) == list(SHARED_FIELDS)
    assert "Manga" in shared["values"]
    assert shared["values"]["Series"] == {"value": "", "mixed": True, "dirty": False}
    assert shared["values"]["Publisher"] == {
        "value": "Shueisha",
        "mixed": False,
        "dirty": False,
    }
    assert all(field["dirty"] is False for field in shared["values"].values())
    assert form_from_volumes([]) is None

    merged = merge_load_patch(one, {"Number": "2", "Summary": "Hello"}, "one")
    assert merged["values"]["Number"] == {"value": "2", "dirty": True}
    assert merged["values"]["Summary"]["dirty"] is True
    assert merged["values"]["Series"] == one["values"]["Series"]
    many = merge_load_patch(
        shared,
        {
            "Series": "Claymore",
            "Manga": "YesAndRightToLeft",
            "Number": "2",
            "Title": "Claymore",
        },
        "many",
    )
    assert "Number" not in many["values"]
    assert "Title" not in many["values"]
    assert many["values"]["Series"] == {
        "value": "Claymore",
        "mixed": False,
        "dirty": True,
    }
    assert many["values"]["Manga"]["dirty"] is True
    assert many["values"]["Publisher"]["dirty"] is False


def test_one_save_number_rules(tmp_path: Path) -> None:
    recorder = _Recorder()
    run_save(
        **_save_kwargs(
            recorder,
            paths=["/books/Claymore.cbz"],
            patch={"Number": "9"},
            mode="one",
            volumes=[_volume("/books/Claymore.cbz", number="1")],
        )
    )
    assert recorder.saves == [("/books/Claymore.cbz", {"Number": "9"}, True)]
    assert recorder.posters == ["/books/Claymore.cbz"]

    recorder = _Recorder()
    run_save(
        **_save_kwargs(
            recorder,
            paths=["/books/Claymore v02.cbz"],
            patch={},
            mode="one",
            volumes=[_volume("/books/Claymore v02.cbz", number="")],
        )
    )
    assert recorder.saves == [("/books/Claymore v02.cbz", {"Number": "2"}, True)]

    recorder = _Recorder()
    result = run_save(
        **_save_kwargs(
            recorder,
            paths=["/books/Claymore v02.cbz"],
            patch={},
            mode="one",
            volumes=[_volume("/books/Claymore v02.cbz", number="2")],
        )
    )
    assert recorder.saves == []
    assert result == {"entries": []}

    recorder = _Recorder()
    run_save(
        **_save_kwargs(
            recorder,
            paths=["/books/Claymore v02.cbz"],
            patch={},
            mode="one",
            volumes=[
                _volume(
                    "/books/Claymore v02.cbz",
                    number="2",
                    page_count="",
                    archive_page_count=42,
                )
            ],
        )
    )
    assert recorder.saves == [
        ("/books/Claymore v02.cbz", {"PageCount": "42"}, False)
    ]

    recorder = _Recorder()
    run_save(
        **_save_kwargs(
            recorder,
            paths=["/books/Claymore.cbz"],
            patch={"PageCount": ""},
            mode="one",
            volumes=[
                _volume(
                    "/books/Claymore.cbz",
                    number="1",
                    page_count="",
                    archive_page_count=42,
                )
            ],
        )
    )
    assert recorder.saves == [("/books/Claymore.cbz", {"PageCount": ""}, False)]


def test_many_save_per_file_number(tmp_path: Path) -> None:
    recorder = _Recorder()
    run_save(
        **_save_kwargs(
            recorder,
            paths=[
                "/books/Claymore v02.cbz",
                "/books/Other v01.cbz",
                "/books/Same v03.cbz",
            ],
            patch={"Publisher": "Shueisha"},
            mode="many",
            volumes=[
                _volume("/books/Claymore v02.cbz", number=""),
                _volume("/books/Other v01.cbz", number="1"),
                _volume("/books/Same v03.cbz", number="3"),
            ],
        )
    )
    assert recorder.saves == [
        (
            "/books/Claymore v02.cbz",
            {"Publisher": "Shueisha", "Number": "2"},
            True,
        ),
        ("/books/Other v01.cbz", {"Publisher": "Shueisha"}, False),
        ("/books/Same v03.cbz", {"Publisher": "Shueisha"}, False),
    ]
    assert all("Series" not in patch for _path, patch, _flag in recorder.saves)
    assert "Volume" not in recorder.saves[0][1]

    recorder = _Recorder()
    run_save(
        **_save_kwargs(
            recorder,
            paths=["/books/Same v03.cbz"],
            patch={},
            mode="many",
            volumes=[_volume("/books/Same v03.cbz", number="3")],
        )
    )
    assert recorder.saves == []

    recorder = _Recorder()
    with pytest.raises(BatchFieldError):
        run_save(
            **_save_kwargs(
                recorder,
                paths=["/books/a.cbz", "/books/b.cbz"],
                patch={"Title": "Nope"},
                mode="many",
                volumes=[_volume("/books/a.cbz"), _volume("/books/b.cbz")],
            )
        )
    assert recorder.saves == []


def test_save_cancel_stops_before_the_next_file() -> None:
    runner = JobRunner(inline=True)
    recorder = _Recorder()
    paths = ["/books/a.cbz", "/books/b.cbz"]

    def save_comic_info(path, patch, *, write_number, keep_cbr_original):
        job = runner.current()
        assert job is not None
        recorder.seen_progress.append((job.completed, job.total))
        recorder.saves.append((path, dict(patch), write_number))
        if len(recorder.saves) == 1:
            runner.cancel(job.id)
        return Path(path)

    recorder.save_comic_info = save_comic_info
    job = runner.start(
        "Save",
        lambda cancel, progress: run_save(
            **_save_kwargs(
                recorder,
                paths=paths,
                patch={"Series": "Claymore"},
                mode="many",
                volumes=[_volume(path, series="Old") for path in paths],
                cancel=cancel,
                progress=progress,
            )
        ),
    )
    assert job.state == "cancelled"
    assert [item[0] for item in recorder.saves] == ["/books/a.cbz"]
    assert recorder.refreshed == ["/books/a.cbz"]
    assert recorder.seen_progress[0] == (0, 2)
    assert job.completed == 1 and job.total == 2
    assert job.result["entries"][0]["output_path"] == "/books/a.cbz"


def test_search_and_load_do_not_write() -> None:
    writes: list[str] = []

    def search(*_args, **_kwargs):
        class Hit:
            id = "1"
            title = "Claymore"
            year = "2001"
            credit = "Yagi"
            count = "27"
            summary = "A claymore story."
            cover = "https://example.com/cover.jpg"

        return [Hit()]

    result = run_search(
        provider="mangadex",
        series="Claymore",
        filename_stem="Claymore v02",
        title_languages=["fr", "en"],
        api_key="",
        nautiljon_base_url="",
        nautiljon_api_key="",
        build_query=lambda series, stem: series or stem,
        search=search,
        client_factory=default_client,
        cancel=lambda: False,
        progress=lambda _completed, _total: writes.append("progress"),
    )
    assert result["candidates"] == [
        {
            "id": "1",
            "title": "Claymore",
            "year": "2001",
            "credit": "Yagi",
            "count": "27",
            "summary": "A claymore story.",
            "cover": "https://example.com/cover.jpg",
        }
    ]
    client = default_client()
    assert client.timeout == httpx.Timeout(15.0)
    client.close()

    form = form_from_volumes(
        [
            _volume("/books/a.cbz", series="A"),
            _volume("/books/b.cbz", series="B"),
        ]
    )
    loaded = run_load(
        provider="mangadex",
        match_id="1",
        filename_stem="Claymore v02",
        mode="many",
        form=form,
        title_languages=["fr", "en"],
        api_key="",
        nautiljon_base_url="",
        nautiljon_api_key="",
        load=lambda *_args, **_kwargs: {
            "Series": "Claymore",
            "Manga": "YesAndRightToLeft",
            "Number": "2",
            "Title": "Claymore",
        },
        client_factory=default_client,
        cancel=lambda: False,
        progress=lambda _completed, _total: None,
    )
    assert "Number" not in loaded["form"]["values"]
    assert loaded["form"]["values"]["Series"]["value"] == "Claymore"
    assert writes == ["progress", "progress"]


def test_list_issues_and_preferred_number() -> None:
    form = form_from_volumes([_volume("/books/a.cbz", series="A", number="3")])
    assert preferred_load_number(form) == "3"
    blank = form_from_volumes([_volume("/books/a.cbz", series="A", number="")])
    assert preferred_load_number(blank) is None

    def list_issues(*_args, **_kwargs):
        class Hit:
            id = "10"
            number = "1"
            title = "First"
            date = "2001-03"
            cover = ""
            summary = ""

        return [Hit()]

    result = run_list_issues(
        provider="comicvine",
        match_id="12345",
        title_languages=["en"],
        api_key="secret",
        nautiljon_base_url="",
        nautiljon_api_key="",
        list_issues=list_issues,
        client_factory=default_client,
        cancel=lambda: False,
        progress=lambda _completed, _total: None,
    )
    assert result["issues"] == [
        {
            "id": "10",
            "number": "1",
            "title": "First",
            "date": "2001-03",
            "cover": "",
            "summary": "",
        }
    ]

    captured: dict[str, object] = {}

    def load(*_args, **kwargs):
        captured.update(kwargs)
        return {"Series": "Claymore", "Number": "3"}

    one = form_from_volumes([_volume("/books/a.cbz", series="A", number="3")])
    run_load(
        provider="comicvine",
        match_id="12345",
        filename_stem="Claymore v02",
        mode="one",
        form=one,
        title_languages=["en"],
        api_key="secret",
        nautiljon_base_url="",
        nautiljon_api_key="",
        load=load,
        client_factory=default_client,
        cancel=lambda: False,
        progress=lambda _completed, _total: None,
        issue_id="99",
    )
    assert captured["issue_id"] == "99"
    assert captured["number"] == "3"


def test_scan_cancel_and_index_error() -> None:
    def cancelled_scan(*_args, **_kwargs):
        return ScanResult((), (), (), (), (), True)

    with pytest.raises(JobCancelled) as raised:
        run_scan(
            db_path="index.db",
            cache_dir="covers",
            roots=["/books"],
            scan=cancelled_scan,
            cancel=lambda: False,
            progress=lambda _completed, _total: None,
        )
    assert raised.value.result["cancelled"] is True

    def broken_scan(*_args, **_kwargs):
        raise LibraryIndexError("bad index")

    runner = JobRunner(inline=True)
    job = runner.start(
        "Scan",
        lambda cancel, progress: run_scan(
            db_path="index.db",
            cache_dir="covers",
            roots=["/books"],
            scan=broken_scan,
            cancel=cancel,
            progress=progress,
        ),
    )
    assert job.state == "failed"
    assert job.error_type == "LibraryIndexError"


def test_rename_preview_and_job(tmp_path: Path) -> None:
    planned: list[tuple[str, str]] = []

    def plan(directory: str, template: str):
        planned.append((directory, template))
        return []

    def rename(*_args, **_kwargs):
        raise AssertionError("rename_in_directory")

    preview_rename(
        "/books/Claymore",
        OFFERED_RENAME_TEMPLATE,
        ["/books"],
        plan_rename=plan,
    )
    assert planned == [("/books/Claymore", OFFERED_RENAME_TEMPLATE)]

    recorder = _Recorder()
    source = Path("/books/Claymore/old.cbz")
    dest = Path("/books/Claymore/Claymore v01.cbz")

    def rename_in_directory(directory: str, template: str):
        recorder.renames.append((directory, template))
        return [FileResult(path=source, output_path=dest)]

    result = run_rename(
        directory="/books/Claymore",
        template=OFFERED_RENAME_TEMPLATE,
        roots=["/books"],
        db_path=str(tmp_path / "index.db"),
        cache_dir=str(tmp_path / "covers"),
        rename_in_directory=rename_in_directory,
        write_poster=recorder.write_poster,
        refresh_volume=recorder.refresh_volume,
        forget_volume=recorder.forget_volume,
        cancel=lambda: False,
        progress=lambda _completed, _total: None,
    )
    assert recorder.renames == [("/books/Claymore", OFFERED_RENAME_TEMPLATE)]
    assert recorder.posters == [str(dest)]
    assert recorder.refreshed == [str(dest)]
    assert recorder.forgot == [str(source)]
    assert result["entries"][0]["output_path"] == str(dest)


def test_convert_skips_cbz_and_does_not_write_a_poster(tmp_path: Path) -> None:
    recorder = _Recorder()

    def convert_cbr(path, *, keep_cbr_original):
        recorder.converted.append((path, keep_cbr_original))
        return Path(path).with_suffix(".cbz")

    result = run_convert(
        paths=["/books/done.CBZ", "/books/old.cbr"],
        roots=["/books"],
        keep_cbr_original=False,
        db_path=str(tmp_path / "index.db"),
        cache_dir=str(tmp_path / "covers"),
        convert_cbr=convert_cbr,
        refresh_volume=recorder.refresh_volume,
        forget_volume=recorder.forget_volume,
        cancel=lambda: False,
        progress=lambda _completed, _total: None,
    )
    assert result["entries"][0] == {"path": "/books/done.CBZ", "skipped": True}
    assert recorder.converted == [("/books/old.cbr", False)]
    assert recorder.posters == []
    assert recorder.refreshed == ["/books/old.cbz"]
    assert recorder.forgot == ["/books/old.cbr"]


def test_runner_queue_cancel_and_busy() -> None:
    runner = JobRunner(hold=True)
    called: list[str] = []
    job = runner.start("Scan", lambda _cancel, _progress: called.append("scan"))
    assert job.state == "queued" and job.id == "1" and job.completed == 0
    with pytest.raises(JobBusyError):
        runner.start("Save", lambda _cancel, _progress: called.append("save"))
    cancelled = runner.cancel(job.id)
    assert cancelled.state == "cancelled"
    runner.release()
    runner.shutdown()
    assert called == []

    inline = JobRunner(inline=True)

    def outer(cancel, progress):
        del cancel, progress
        with pytest.raises(JobBusyError):
            inline.start("Save", lambda _cancel, _progress: called.append("inner"))

    finished = inline.start("Scan", outer)
    assert finished.state == "succeeded"
    assert called == []


def _volume(path: str, **overrides: object) -> Volume:
    name = Path(path).name
    values: dict[str, object] = {
        "path": path,
        "root": str(Path(path).parent),
        "name": name,
        "extension": Path(name).suffix,
        "size": 1,
        "mtime_ns": 1,
        "status": "ok",
        "error_type": "",
        "error_message": "",
        "cover_index": 0,
        "archive_page_count": 1,
        "title": "",
        "series": "",
        "number": "",
        "volume": "",
        "publisher": "",
        "page_count": "1",
        "language_iso": "",
        "age_rating": "",
        "manga": "",
        "genre": "",
        "summary": "",
        "web": "",
        "community_rating": "",
        "notes": "",
        "year": "",
        "month": "",
        "day": "",
        "writer": "",
        "penciller": "",
        "inker": "",
        "cover_artist": "",
    }
    values.update(overrides)
    return Volume(**values)


class _Recorder:
    def __init__(self) -> None:
        self.saves: list[tuple[str, dict[str, str], bool]] = []
        self.posters: list[str] = []
        self.refreshed: list[str] = []
        self.forgot: list[str] = []
        self.renames: list[tuple[str, str]] = []
        self.converted: list[tuple[str, bool]] = []
        self.seen_progress: list[tuple[int, int]] = []

    def save_comic_info(self, path, patch, *, write_number, keep_cbr_original):
        del keep_cbr_original
        self.saves.append((path, dict(patch), write_number))
        return Path(path)

    def write_poster(self, path: str) -> None:
        self.posters.append(path)

    def refresh_volume(self, db_path, path, roots) -> None:
        del db_path, roots
        self.refreshed.append(path)

    def forget_volume(self, db_path, cache_dir, path) -> None:
        del db_path, cache_dir
        self.forgot.append(path)


def _save_kwargs(recorder: _Recorder, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "paths": [],
        "patch": {},
        "mode": "one",
        "volumes": [],
        "roots": ["/books"],
        "keep_cbr_original": False,
        "db_path": "index.db",
        "cache_dir": "covers",
        "save_comic_info": recorder.save_comic_info,
        "write_poster": recorder.write_poster,
        "refresh_volume": recorder.refresh_volume,
        "forget_volume": recorder.forget_volume,
        "parse_number": parse_number,
        "cancel": lambda: False,
        "progress": lambda _completed, _total: None,
    }
    values.update(overrides)
    return values
