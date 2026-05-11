from datetime import date
from pathlib import Path

import pytest

from app.wiki import Wiki


@pytest.fixture
def wiki(tmp_path: Path) -> Wiki:
    w = Wiki(tmp_path / "ws")
    w.ensure()
    return w


def test_ensure_creates_layout(wiki: Wiki):
    assert (wiki.root / "raw").is_dir()
    assert (wiki.root / "wiki").is_dir()
    assert (wiki.root / "index.md").is_file()
    assert (wiki.root / "log.md").is_file()
    assert (wiki.root / "SCHEMA.md").is_file()


def test_ensure_is_idempotent_and_preserves_content(wiki: Wiki):
    wiki.write_index("# my index\n")
    wiki.ensure()
    assert wiki.read_index() == "# my index\n"


def test_write_and_read_page(wiki: Wiki):
    wiki.write_page("mitochondria", "# Mitochondria\n\nPower of the cell.\n")
    assert wiki.list_pages() == ["mitochondria"]
    assert wiki.page_exists("mitochondria")
    assert "Power of the cell" in wiki.read_page("mitochondria")


def test_invalid_slug_rejected(wiki: Wiki):
    for bad in ["Bad Name", "bad/name", "../escape", "BAD", ""]:
        with pytest.raises(ValueError):
            wiki.write_page(bad, "x")


def test_path_traversal_blocked(wiki: Wiki):
    # Even valid-looking slugs cannot escape; the slug regex prevents `..` etc.
    with pytest.raises(ValueError):
        wiki.read_page("..")


def test_read_missing_page_raises(wiki: Wiki):
    with pytest.raises(FileNotFoundError):
        wiki.read_page("nope")


def test_append_log_adds_dated_entry(wiki: Wiki):
    header = wiki.log_entry_header("ingest", "First Source")
    wiki.append_log(f"{header}\n\nDid stuff.")
    log = wiki.read_log()
    assert f"## [{date.today().isoformat()}] ingest | First Source" in log
    assert "Did stuff." in log


def test_raw_round_trip(wiki: Wiki):
    wiki.write_raw("hello-world", "raw text")
    assert wiki.list_raw() == ["hello-world"]
    assert wiki.read_raw("hello-world") == "raw text"


def test_delete_page(wiki: Wiki):
    wiki.write_page("a-page", "x")
    wiki.delete_page("a-page")
    assert not wiki.page_exists("a-page")
    # Deleting a non-existent page should be a no-op, not an error.
    wiki.delete_page("a-page")
