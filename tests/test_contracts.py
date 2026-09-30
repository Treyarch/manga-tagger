"""Cross-layer contracts mirrored by the Svelte client."""

import json
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

from manga_tagger.api.models import JobModel
from manga_tagger.archives.comicinfo import OWNED_ELEMENTS
from manga_tagger.index import ScanResult
from manga_tagger.providers.constants import PROVIDER_IDS
from manga_tagger.providers.service_types import Candidate, IssueCandidate
from manga_tagger.shell import (
    FIELD_COLUMNS,
    FORM_FIELDS,
    SHARED_FIELDS,
    _after_success,
    _error_entry,
    _scan_payload,
    form_from_volumes,
    run_convert,
)


def _contract() -> dict[str, object]:
    path = Path(__file__).parent / "contracts" / "app-contracts.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _row(**updates: object) -> SimpleNamespace:
    values: dict[str, object] = {
        column: "" for column in FIELD_COLUMNS.values()
    }
    values.update(archive_page_count=3, locked_fields="[]")
    values.update(updates)
    return SimpleNamespace(**values)


def test_python_contracts_match_shared_fixture() -> None:
    contract = _contract()

    assert list(FORM_FIELDS) == contract["form_fields"]
    assert list(OWNED_ELEMENTS) == contract["rename_tags"]
    assert list(SHARED_FIELDS) == contract["shared_fields"]
    assert {name: FIELD_COLUMNS[name] for name in FORM_FIELDS} == contract[
        "field_columns"
    ]
    assert list(FORM_FIELDS) == contract["lockable_fields"]
    assert list(PROVIDER_IDS) == contract["provider_ids"]

    one = form_from_volumes([_row(number="1")])
    many = form_from_volumes([_row(series="A"), _row(series="B")])
    assert one is not None and list(one["values"]) == contract["form_fields"]
    assert many is not None and list(many["values"]) == contract["shared_fields"]


def test_python_api_result_keys_match_shared_fixture() -> None:
    result_keys = _contract()["api_result_keys"]

    assert list(JobModel.model_fields) == result_keys["job"]
    scan = ScanResult((), (), (), (), (), (), False)
    assert list(_scan_payload(scan)) == result_keys["scan"]
    assert [field.name for field in fields(Candidate)] == result_keys["candidate"]
    assert [field.name for field in fields(IssueCandidate)] == result_keys["issue"]

    success = _after_success(
        "/books/a.cbr",
        Path("/books/a.cbz"),
        db_path="index.db",
        cache_dir="covers",
        roots=["/books"],
        write_poster=lambda _path: None,
        refresh_volume=lambda *_args: None,
        forget_volume=lambda *_args: None,
        copy_locked_fields=lambda *_args: None,
        with_poster=False,
    )
    error = _error_entry("/books/a.cbr", ValueError("bad"))
    skipped = run_convert(
        paths=["/books/a.cbz"],
        roots=["/books"],
        keep_cbr_original=True,
        db_path="index.db",
        cache_dir="covers",
        convert_cbr=lambda *_args, **_kwargs: Path("/books/a.cbz"),
        refresh_volume=lambda *_args: None,
        forget_volume=lambda *_args: None,
        copy_locked_fields=lambda *_args: None,
        cancel=lambda: False,
        progress=lambda *_args: None,
    )["entries"][0]
    work_keys = set(success) | set(error) | set(skipped)
    assert work_keys == set(result_keys["work_entry"])
