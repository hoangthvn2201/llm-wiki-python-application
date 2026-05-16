from datetime import date
from pathlib import Path

import pytest

from app.wiki import DEFAULT_SCHEMA, Wiki, _ensure_slug


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


# =================================================== _ensure_slug edge cases

def test_ensure_slug_strips_surrounding_whitespace():
    assert _ensure_slug("  alpha  ") == "alpha"


def test_ensure_slug_returns_stripped_canonical_form():
    assert _ensure_slug("\talpha-beta\n") == "alpha-beta"


# =========================================================== Wiki.__init__

def test_init_expands_user_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    w = Wiki(Path("~/ws"))

    assert w.root == (tmp_path / "ws").resolve()


def test_init_resolves_relative_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)

    w = Wiki(Path("relative-ws"))

    assert w.root.is_absolute()
    assert w.root == (tmp_path / "relative-ws").resolve()


def test_init_does_not_touch_filesystem(tmp_path: Path):
    target = tmp_path / "never-created"

    Wiki(target)

    assert not target.exists()


# ============================================================ ensure() defaults

def test_ensure_seeds_default_index_with_section_headers(wiki: Wiki):
    index = wiki.read_index()

    for header in ("## Entities", "## Concepts", "## Sources", "## Reports"):
        assert header in index


def test_ensure_seeds_default_schema_equal_to_constant(wiki: Wiki):
    assert wiki.read_schema() == DEFAULT_SCHEMA


def test_ensure_seeds_log_with_log_heading(wiki: Wiki):
    assert wiki.read_log() == "# Log\n\n"


def test_ensure_does_not_overwrite_custom_schema(wiki: Wiki):
    wiki.write_schema("# Custom\n")

    wiki.ensure()

    assert wiki.read_schema() == "# Custom\n"


# ============================================================== _safe_path

def test_safe_path_returns_path_under_root(wiki: Wiki):
    # Positive case — pin that the helper doesn't refuse legitimate paths.
    p = wiki._safe_path("wiki", "alpha.md")

    assert p == (wiki.root / "wiki" / "alpha.md").resolve()


def test_safe_path_rejects_absolute_path_injection(wiki: Wiki):
    # `Path("/etc/passwd")` would replace the root via joinpath; the helper
    # must catch that.
    with pytest.raises(ValueError):
        wiki._safe_path("/etc/passwd")


# =============================================================== list_pages

def test_list_pages_empty(wiki: Wiki):
    assert wiki.list_pages() == []


def test_list_pages_ignores_non_md_files_and_subdirs(wiki: Wiki):
    (wiki.root / "wiki" / "alpha.md").write_text("# a")
    (wiki.root / "wiki" / "notes.txt").write_text("ignored")
    (wiki.root / "wiki" / "subdir").mkdir()
    (wiki.root / "wiki" / "subdir" / "nested.md").write_text("ignored")

    assert wiki.list_pages() == ["alpha"]


# ============================================== invalid slug on read paths

def test_read_page_invalid_slug_raises_value_error(wiki: Wiki):
    with pytest.raises(ValueError):
        wiki.read_page("Bad Slug")


def test_page_exists_invalid_slug_raises_value_error(wiki: Wiki):
    with pytest.raises(ValueError):
        wiki.page_exists("Bad Slug")


def test_delete_page_invalid_slug_raises_value_error(wiki: Wiki):
    with pytest.raises(ValueError):
        wiki.delete_page("Bad Slug")


# ================================================================ write_page

def test_write_page_overwrites_existing_content(wiki: Wiki):
    wiki.write_page("alpha", "# v1\n")
    wiki.write_page("alpha", "# v2\n")

    assert wiki.read_page("alpha") == "# v2\n"


def test_write_page_round_trips_non_ascii(wiki: Wiki):
    content = "# Mitochondrion 🔋\n\nVoilà — café résumé.\n"
    wiki.write_page("mito", content)

    assert wiki.read_page("mito") == content


# =========================================================== index round-trip

def test_index_round_trip(wiki: Wiki):
    wiki.write_index("# Custom Index\n")

    assert wiki.read_index() == "# Custom Index\n"


# ======================================================== append_log edges

def test_append_log_inserts_blank_line_separator_between_entries(wiki: Wiki):
    wiki.append_log("## entry one\nbody one")
    wiki.append_log("## entry two")

    log = wiki.read_log()
    assert "## entry one" in log
    assert "## entry two" in log
    # The two entries are separated by a blank line.
    assert "body one\n\n## entry two" in log


def test_append_log_strips_trailing_whitespace_from_entry(wiki: Wiki):
    wiki.append_log("## entry one\nbody   \n\n\t  ")

    log = wiki.read_log()
    # The function rstrips the entry and adds exactly one trailing newline.
    assert log.endswith("body\n")
    assert not log.endswith("  \n")


def test_append_log_initialises_when_log_missing(wiki: Wiki):
    (wiki.root / "log.md").unlink()

    wiki.append_log("## fresh entry")

    log = wiki.read_log()
    assert log.startswith("# Log\n\n")
    assert "## fresh entry" in log


def test_append_log_inserts_separator_when_existing_lacks_blank_line(wiki: Wiki):
    # Manually write a log that ends with a single newline, not a blank line.
    (wiki.root / "log.md").write_text("# Log\nNo trailing blank")

    wiki.append_log("## new entry")

    log = wiki.read_log()
    assert "No trailing blank\n\n## new entry" in log


# ============================================================ log_entry_header

def test_log_entry_header_format(wiki: Wiki):
    header = wiki.log_entry_header("ingest", "My Title")

    assert header == f"## [{date.today().isoformat()}] ingest | My Title"


# ============================================================= schema r/w

def test_schema_round_trip(wiki: Wiki):
    wiki.write_schema("# Custom\n\nNotes.\n")

    assert wiki.read_schema() == "# Custom\n\nNotes.\n"


# ================================================================= raw edges

def test_write_raw_returns_resolved_path(wiki: Wiki):
    p = wiki.write_raw("hello-world", "raw text")

    assert p == (wiki.root / "raw" / "hello-world.md").resolve()
    assert p.is_file()


def test_read_raw_missing_raises_file_not_found(wiki: Wiki):
    with pytest.raises(FileNotFoundError):
        wiki.read_raw("does-not-exist")


def test_read_raw_invalid_slug_raises_value_error(wiki: Wiki):
    with pytest.raises(ValueError):
        wiki.read_raw("Bad Slug")


def test_list_raw_empty(wiki: Wiki):
    assert wiki.list_raw() == []


def test_list_raw_returns_sorted_slugs(wiki: Wiki):
    wiki.write_raw("beta", "b")
    wiki.write_raw("alpha", "a")

    assert wiki.list_raw() == ["alpha", "beta"]
