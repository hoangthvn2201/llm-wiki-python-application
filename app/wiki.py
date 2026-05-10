"""Pure filesystem operations on the wiki workspace.

No LLM calls here. Every name argument is validated as a kebab-case slug and
every path is resolved under the workspace root to prevent traversal.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

DEFAULT_SCHEMA = """# Wiki Schema

Conventions the LLM follows when maintaining this wiki. Edit freely — you and the LLM co-evolve this.

## Layout

- `raw/` — source documents. Immutable. The LLM reads but never writes here.
- `wiki/` — LLM-generated pages. One concept, entity, or topic per file.
- `index.md` — catalog of every wiki page, grouped by category.
- `log.md` — append-only chronological record of ingests, queries, and lint passes.

## Page naming

- Kebab-case slugs only: `mitochondria.md`, `napoleon-in-russia.md`.
- Names must match `^[a-z0-9][a-z0-9-]*$`.
- Prefer specific, descriptive names over generic ones.

## Page structure

```markdown
# Page Title

(Optional one-line summary)

## Body

Rich content with [[cross-references]] to other pages.

## Sources

- raw/source-name.md
```

## Cross-references

Use `[[page-name]]` (Obsidian-style) when referring to another wiki page.

## When to create vs update

- If a page already exists for the entity/concept, **update** it — extend, refine, or correct.
- Only create a new page when the topic is genuinely new.
- Keep pages focused. Split when a page becomes a grab-bag.

## index.md

Group pages by category. Each entry: `- [name](wiki/name.md) — one-line summary`.

Suggested sections: Entities, Concepts, Sources, Reports.

## log.md

Each entry begins with a header on its own line:

```
## [YYYY-MM-DD] <op> | <title>
```

Where `<op>` is one of `ingest`, `query`, `lint`. Body is a short note about what happened.
"""


def _ensure_slug(name: str) -> str:
    stripped = name.strip()
    if not SLUG_RE.match(stripped):
        raise ValueError(
            f"Invalid name {name!r}: must be kebab-case (lowercase letters, digits, hyphens; "
            "must start with a letter or digit)."
        )
    return stripped


class Wiki:
    """A wiki workspace rooted at a single directory."""

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()

    # ------------------------------------------------------------------ setup

    def ensure(self) -> None:
        """Create the workspace structure on disk if missing."""
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "raw").mkdir(exist_ok=True)
        (self.root / "wiki").mkdir(exist_ok=True)
        if not (self.root / "index.md").exists():
            (self.root / "index.md").write_text(
                "# Index\n\nThe wiki is empty. Ingest a source to begin.\n\n"
                "## Entities\n\n## Concepts\n\n## Sources\n\n## Reports\n",
                encoding="utf-8",
            )
        if not (self.root / "log.md").exists():
            (self.root / "log.md").write_text("# Log\n\n", encoding="utf-8")
        if not (self.root / "SCHEMA.md").exists():
            (self.root / "SCHEMA.md").write_text(DEFAULT_SCHEMA, encoding="utf-8")

    # --------------------------------------------------------------- helpers

    def _safe_path(self, *parts: str) -> Path:
        candidate = (self.root.joinpath(*parts)).resolve()
        if self.root not in candidate.parents and candidate != self.root:
            raise ValueError(f"Path {candidate} escapes workspace root {self.root}")
        return candidate

    # -------------------------------------------------------------- wiki pgs

    def list_pages(self) -> list[str]:
        wiki_dir = self.root / "wiki"
        return sorted(p.stem for p in wiki_dir.glob("*.md"))

    def page_exists(self, name: str) -> bool:
        name = _ensure_slug(name)
        return self._safe_path("wiki", f"{name}.md").exists()

    def read_page(self, name: str) -> str:
        name = _ensure_slug(name)
        path = self._safe_path("wiki", f"{name}.md")
        if not path.exists():
            raise FileNotFoundError(f"Page {name!r} does not exist.")
        return path.read_text(encoding="utf-8")

    def write_page(self, name: str, content: str) -> None:
        name = _ensure_slug(name)
        path = self._safe_path("wiki", f"{name}.md")
        path.write_text(content, encoding="utf-8")

    def delete_page(self, name: str) -> None:
        name = _ensure_slug(name)
        path = self._safe_path("wiki", f"{name}.md")
        if path.exists():
            path.unlink()

    # ----------------------------------------------------------------- index

    def read_index(self) -> str:
        return (self.root / "index.md").read_text(encoding="utf-8")

    def write_index(self, content: str) -> None:
        (self.root / "index.md").write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------- log

    def read_log(self) -> str:
        return (self.root / "log.md").read_text(encoding="utf-8")

    def append_log(self, entry: str) -> None:
        log_path = self.root / "log.md"
        existing = log_path.read_text(encoding="utf-8") if log_path.exists() else "# Log\n\n"
        if not existing.endswith("\n"):
            existing += "\n"
        if not existing.endswith("\n\n"):
            existing += "\n"
        log_path.write_text(existing + entry.rstrip() + "\n", encoding="utf-8")

    def log_entry_header(self, op: str, title: str) -> str:
        return f"## [{date.today().isoformat()}] {op} | {title}"

    # ---------------------------------------------------------------- schema

    def read_schema(self) -> str:
        return (self.root / "SCHEMA.md").read_text(encoding="utf-8")

    def write_schema(self, content: str) -> None:
        (self.root / "SCHEMA.md").write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------- raw

    def list_raw(self) -> list[str]:
        return sorted(p.stem for p in (self.root / "raw").glob("*.md"))

    def read_raw(self, name: str) -> str:
        name = _ensure_slug(name)
        path = self._safe_path("raw", f"{name}.md")
        if not path.exists():
            raise FileNotFoundError(f"Raw source {name!r} does not exist.")
        return path.read_text(encoding="utf-8")

    def write_raw(self, name: str, content: str) -> Path:
        name = _ensure_slug(name)
        path = self._safe_path("raw", f"{name}.md")
        path.write_text(content, encoding="utf-8")
        return path
