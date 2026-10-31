"""Publish reviewed docs to Confluence, or render them locally (dry run, the default).

Usage:
    python -m scripts.publish_confluence [--include-drafts] [--out build/confluence]
    python -m scripts.publish_confluence --live

Git stays the source of truth; Confluence gets a read-only copy.
    selection  packages whose entry in state/doc-status.json is `approved` or `stale`, with their
               unit docs, plus the glossary and a generated root page. An approved entry whose
               source hash no longer matches legacy_code/ is published as stale. --include-drafts
               also renders draft and reviewed docs, in a dry run only
    previous   a package that was approved before but is now draft or reviewed (for example
               after update-package) keeps its last approved version, read from git history,
               with a banner saying a newer version is in review; stale if its source changed
    conversion markdown -> Confluence storage format, without an LLM: citations become links to
               the source at the current commit (SOURCE_BASE_URL), "Open questions" becomes a
               task list, and every page starts with a "generated, do not edit" banner
    live       creates or updates pages by title in CONFLUENCE_SPACE (the root page under
               CONFLUENCE_PARENT_ID when set) through the REST API, skips pages whose
               fingerprint (doc text, status, source hash) is unchanged, and refuses to touch a
               page this script did not generate. Needs a clean working tree
    labels     every page is labeled ai-generated; package and unit pages also get their status
               (approved or stale). Labels are kept in sync, also on unchanged pages. The same
               names open each page as coloured status lozenges, right under the title

The dry run writes one .xhtml file per page and pages.json to --out, and calls nothing.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path, PurePosixPath

from dotenv import load_dotenv

from pydantic import ValidationError

from scripts.extract_metadata import REPO_ROOT
from scripts.gitutil import checkout
from scripts.gitutil import git as git_at
from scripts.models import DocState, DocStatusEntry, DocStatusFile
from scripts.validate_doc import CITATION_RE, Metadata, inside, load_metadata

ROOT_TITLE = "Legacy PL/SQL documentation"
ROOT_SOURCE = "state/doc-status.json"
OPEN_QUESTIONS = "Open questions"
PUBLISHED = {DocState.APPROVED, DocState.STALE}
PREVIEW = PUBLISHED | {DocState.DRAFT, DocState.REVIEWED}
LIVE_ENV = ("CONFLUENCE_SITE", "CONFLUENCE_SPACE", "ATLASSIAN_EMAIL", "ATLASSIAN_TOKEN")
GIT_PATHS = ("docs", "glossary", "state", "legacy_code")
AI_LABEL = "ai-generated"
STATUS_LABELS = {str(s) for s in PREVIEW}  # the script removes these when the status changes
BADGE_COLOURS = {AI_LABEL: "Purple", DocState.APPROVED: "Green", DocState.STALE: "Yellow",
                 DocState.REVIEWED: "Blue", DocState.DRAFT: "Grey"}
FORMAT = "2"  # part of every fingerprint: bump it when the rendering changes, so all pages are updated
PREVIOUS_NOTE = ("A newer version of this doc is being reviewed. Until it is approved, this page shows "
                 "the last approved version. ")
CHECKOUT_PATHS = ["state", "docs", "metadata", "legacy_code"]  # what a previous version is rendered from

ITEM_RE = re.compile(r"\s*([-*+]|\d+\.)\s+(.*)")
TOKEN_RE = re.compile(r"(?P<cit>\[[A-Za-z0-9_$#.()/\-]+:\d+(?:-\d+)?\])"
                      r"|\[(?P<text>[^\]]+)\]\((?P<href>[^)\s]+)\)"
                      r"|\*\*(?P<bold>.+?)\*\*")


class PublishError(Exception):
    pass


@dataclass
class Page:
    title: str
    parent: str | None  # parent page title; None for the root page
    source: str         # repo path the page is generated from; also its ownership marker
    status: str
    fingerprint: str
    body: str           # storage format, banner included
    previous: str = ""  # commit of the last approved version shown instead of a newer, unapproved doc

    @property
    def labels(self) -> list[str]:
        return [AI_LABEL] + ([self.status] if self.status in STATUS_LABELS else [])


# ---------------------------------------------------------------------------
# Markdown -> storage format
# ---------------------------------------------------------------------------

def cdata(text: str) -> str:
    return "<![CDATA[" + text.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def split_cells(line: str) -> list[str]:
    """Cells of a table row; a | inside a code span does not split."""
    cells, cell, in_code = [], "", False
    for ch in line.strip().strip("|"):
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            cells.append(cell.strip())
            cell = ""
        else:
            cell += ch
    return cells + [cell.strip()]


def title_of(text: str) -> str:
    first = next((ln for ln in text.splitlines() if ln.startswith("# ")), "# untitled")
    return first[2:].replace("`", "").strip()


@dataclass
class Converter:
    meta: Metadata
    titles: dict[str, str]  # repo path of a published doc -> page title
    commit: str
    source_base: str        # e.g. https://github.com/<owner>/<repo>/blob; empty = no source links

    def inline(self, text: str, doc_dir: PurePosixPath) -> str:
        out = []
        for i, part in enumerate(re.split(r"`([^`]+)`", text)):
            out.append(f"<code>{escape(part)}</code>" if i % 2 else self.prose(part, doc_dir))
        return "".join(out)

    def prose(self, text: str, doc_dir: PurePosixPath) -> str:
        out, pos = [], 0
        for m in TOKEN_RE.finditer(text):
            out.append(escape(text[pos:m.start()]))
            if m["cit"]:
                out.append(self.citation(m["cit"]))
            elif m["bold"]:
                out.append(f"<strong>{self.prose(m['bold'], doc_dir)}</strong>")
            else:
                out.append(self.link(m["text"], m["href"], doc_dir))
            pos = m.end()
        return "".join(out) + escape(text[pos:])

    def citation(self, cit: str) -> str:
        m = CITATION_RE.fullmatch(cit)
        start, end = int(m[2]), int(m[3] or m[2])
        refs, error = self.meta.resolve(m[1])
        ref = next((r for r in refs if inside([r], start, end)), None)
        if error or ref is None or not self.source_base:
            return escape(cit)
        url = f"{self.source_base.rstrip('/')}/{self.commit}/{ref.file}#L{start}"
        url += f"-L{end}" if end != start else ""
        return f'<a href="{escape(url)}">{escape(cit)}</a>'

    def link(self, text: str, href: str, doc_dir: PurePosixPath) -> str:
        if href.startswith(("http://", "https://")):
            return f'<a href="{escape(href)}">{escape(text)}</a>'
        target = os.path.normpath(doc_dir / href.split("#")[0]).replace("\\", "/")
        if target not in self.titles:  # not published: keep the text, drop the link
            return escape(text)
        return (f'<ac:link><ri:page ri:content-title="{escape(self.titles[target])}" />'
                f"<ac:plain-text-link-body>{cdata(text)}</ac:plain-text-link-body></ac:link>")

    def convert(self, text: str, path: str) -> str:
        """Storage format for a markdown doc. The "# " title is dropped: Confluence shows it."""
        doc_dir = PurePosixPath(path).parent
        lines = text.replace("\r\n", "\n").split("\n")
        out, section, i = [], None, 0
        while i < len(lines):
            line = lines[i]
            if not line.strip() or line.startswith("# "):
                i += 1
            elif line.lstrip().startswith("```"):
                lang = line.strip()[3:].strip()
                j = i + 1
                while j < len(lines) and not lines[j].lstrip().startswith("```"):
                    j += 1
                param = f'<ac:parameter ac:name="language">{escape(lang)}</ac:parameter>' if lang else ""
                out.append(f'<ac:structured-macro ac:name="code">{param}'
                           f"<ac:plain-text-body>{cdata(chr(10).join(lines[i + 1:j]))}</ac:plain-text-body>"
                           "</ac:structured-macro>")
                i = j + 1
            elif m := re.match(r"(#{2,6}) (.*)", line):
                level, heading = len(m[1]), m[2].strip()
                section = heading if level == 2 else section
                out.append(f"<h{level}>{self.inline(heading, doc_dir)}</h{level}>")
                i += 1
            elif line.lstrip().startswith("|"):
                rows = []
                while i < len(lines) and lines[i].lstrip().startswith("|"):
                    cells = split_cells(lines[i])
                    if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                        tag = "th" if not rows else "td"
                        rows.append("<tr>" + "".join(f"<{tag}>{self.inline(c, doc_dir)}</{tag}>"
                                                     for c in cells) + "</tr>")
                    i += 1
                out.append(f"<table><tbody>{''.join(rows)}</tbody></table>")
            elif m := ITEM_RE.match(line):
                ordered = m[1][0].isdigit()
                items = []
                while i < len(lines) and lines[i].strip() and not self.block_start(lines[i]):
                    m = ITEM_RE.match(lines[i])
                    if m and m[1][0].isdigit() != ordered:
                        break
                    if m:
                        items.append(m[2].strip())
                    else:  # continuation line of the previous item
                        items[-1] += " " + lines[i].strip()
                    i += 1
                out.append(self.list_block(items, ordered, section == OPEN_QUESTIONS, doc_dir))
            else:
                para = []
                while i < len(lines) and lines[i].strip() and not self.block_start(lines[i]) \
                        and not ITEM_RE.match(lines[i]):
                    para.append(lines[i].strip())
                    i += 1
                out.append(f"<p>{self.inline(' '.join(para), doc_dir)}</p>")
        return "".join(out)

    @staticmethod
    def block_start(line: str) -> bool:
        return line.startswith("#") or line.lstrip().startswith(("|", "```"))

    def list_block(self, items: list[str], ordered: bool, tasks: bool, doc_dir: PurePosixPath) -> str:
        if tasks:  # open questions: experts tick them off where they read
            return "<ac:task-list>" + "".join(
                f"<ac:task><ac:task-id>{n}</ac:task-id><ac:task-status>incomplete</ac:task-status>"
                f"<ac:task-body>{self.inline(item, doc_dir)}</ac:task-body></ac:task>"
                for n, item in enumerate(items, 1)) + "</ac:task-list>"
        tag = "ol" if ordered else "ul"
        return f"<{tag}>" + "".join(f"<li>{self.inline(item, doc_dir)}</li>" for item in items) + f"</{tag}>"


# ---------------------------------------------------------------------------
# Page selection
# ---------------------------------------------------------------------------

def source_hash(files: list[str], root: Path) -> str:
    return hashlib.sha256(b"".join((root / f).read_bytes() for f in files)).hexdigest()


def fingerprint(*parts: str) -> str:
    return hashlib.sha256("\n".join((FORMAT, *parts)).encode("utf-8")).hexdigest()[:16]


def badges(status: str) -> str:
    """Coloured status lozenges, the first thing under the page title: AI generated, and the doc status."""
    names = [AI_LABEL] + ([status] if status in STATUS_LABELS else [])
    return "<p>" + " ".join(
        '<ac:structured-macro ac:name="status">'
        f'<ac:parameter ac:name="title">{escape(name.replace("-", " ").upper())}</ac:parameter>'
        f'<ac:parameter ac:name="colour">{BADGE_COLOURS[name]}</ac:parameter></ac:structured-macro>'
        for name in names) + "</p>"


def banner(source: str, status: str, commit: str, fp: str, previous: bool = False) -> str:
    generated = (f"Generated from {source} at commit {commit[:12]}. Do not edit this page: change the "
                 f"markdown in git through a pull request. Status: {status}. Fingerprint: {fp}.")
    lead = PREVIOUS_NOTE if previous else ""
    if status == DocState.STALE:
        kind = "warning"
        lead += ("The PL/SQL source changed after this doc was reviewed (the source hash no longer "
                 "matches). Treat the content as outdated until it is reviewed again. ")
    elif status in (DocState.DRAFT, DocState.REVIEWED):
        kind, lead = "note", "Preview of a doc that is not approved. It is never published with --live. "
    else:
        kind = "note" if previous else "info"
    return (f'<ac:structured-macro ac:name="{kind}"><ac:rich-text-body><p>{escape(lead + generated)}</p>'
            "</ac:rich-text-body></ac:structured-macro>")


def effective_status(entry: DocStatusEntry, root: Path) -> DocState:
    if entry.status == DocState.APPROVED:
        try:
            changed = source_hash(entry.source_files, root) != entry.source_hash
        except FileNotFoundError:  # the source moved or was removed
            changed = True
        return DocState.STALE if changed else DocState.APPROVED
    return entry.status


@dataclass
class Version:
    """The files, metadata and state of one commit: the current one, or the last approved one of a package."""
    root: Path
    meta: Metadata
    commit: str
    state: DocStatusFile | None = None


def last_approved(package: str, root: Path = REPO_ROOT) -> str | None:
    """The newest commit at which state/doc-status.json had the package approved."""
    for commit in git_at(root, "log", "--format=%H", "--", ROOT_SOURCE).decode().split():
        try:
            state = DocStatusFile.model_validate_json(git_at(root, "show", f"{commit}:{ROOT_SOURCE}"))
        except (subprocess.CalledProcessError, ValidationError):
            continue
        entry = state.entries.get(package)
        if entry and entry.status == DocState.APPROVED:
            return commit
    return None


def collect_pages(state: DocStatusFile, meta: Metadata, commit: str, source_base: str,
                  include_drafts: bool = False, glossary: list[str] | None = None,
                  root: Path = REPO_ROOT, previous=None) -> tuple[list[Page], list[str]]:
    """Pages in publish order (parents first), and one line per skipped package.

    previous(package) returns the Version of the package's last approved commit, or None. It is
    used for a package that is not publishable now, so its pages keep the last approved content.
    """
    allowed = PREVIEW if include_drafts else PUBLISHED
    current = Version(root, meta, commit)
    docs, skipped, rows = [], [], []  # docs: (repo path, parent title, status, source hash, version)
    for name, entry in sorted(state.entries.items()):
        status, version = effective_status(entry, root), current
        if status not in allowed:
            version = previous(name) if previous else None
            if version is None:
                skipped.append(f"{name}: status {status}, publishing needs approved")
                continue
            entry = version.state.entries[name]
            status = effective_status(entry, root)  # the old approval against today's source
        package_title = title_of((version.root / entry.doc_path).read_text(encoding="utf-8"))
        docs.append((entry.doc_path, ROOT_TITLE, status, entry.source_hash, version))
        unit_dir = version.root / entry.doc_path[:-len(".md")]
        for unit in sorted(unit_dir.glob("*.md")) if unit_dir.is_dir() else []:
            docs.append((unit.relative_to(version.root).as_posix(), package_title, status, entry.source_hash, version))
        shown = f"{status}, last approved version" if version is not current else str(status)
        rows.append(f"<tr><td>{escape(name)}</td><td>{shown}</td><td><code>{entry.source_hash[:12]}</code></td></tr>")
    for path in glossary or []:
        docs.append((path, ROOT_TITLE, "committed", "", current))

    texts = {path: (version.root / path).read_text(encoding="utf-8") for path, _, _, _, version in docs}
    titles = {path: title_of(text) for path, text in texts.items()}
    if len(set(titles.values())) != len(titles):
        raise PublishError("two docs have the same title; Confluence titles must be unique in a space")
    converters = {}  # one per version: citations link to the source at that version's commit

    index = ('<p>Generated from git. Each page links its claims to the cited source lines.</p>'
             "<table><tbody><tr><th>Package</th><th>Status</th><th>Source hash</th></tr>"
             f"{''.join(rows)}</tbody></table>"
             '<ac:structured-macro ac:name="children" />')
    fp = fingerprint(ROOT_SOURCE, index)
    pages = [Page(ROOT_TITLE, None, ROOT_SOURCE, "generated", fp,
                  badges("generated") + banner(ROOT_SOURCE, "generated", commit, fp) + index)]
    for path, parent, status, src_hash, version in docs:
        conv = converters.setdefault(id(version), Converter(version.meta, titles, version.commit, source_base))
        is_previous = version is not current
        fp = fingerprint(path, status, src_hash, texts[path], *([version.commit] if is_previous else []))
        body = (badges(status) + banner(path, status, version.commit, fp, is_previous)
                + conv.convert(texts[path], path))
        pages.append(Page(titles[path], parent, path, status, fp, body, version.commit if is_previous else ""))
    return pages, skipped


# ---------------------------------------------------------------------------
# Output: dry run or Confluence
# ---------------------------------------------------------------------------

def write_dry_run(pages: list[Page], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for old in [*out.glob("*.xhtml"), out / "pages.json"]:
        old.unlink(missing_ok=True)
    manifest = []
    for n, page in enumerate(pages, 1):
        name = f"{n:02d}-{re.sub(r'[^A-Za-z0-9]+', '_', page.title).strip('_').lower()}.xhtml"
        (out / name).write_text(page.body + "\n", encoding="utf-8", newline="\n")
        manifest.append({**{k: v for k, v in asdict(page).items() if k != "body"}, "labels": page.labels,
                         "file": name})
    (out / "pages.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")


def site_url(site: str) -> str:
    """CONFLUENCE_SITE (yourname.atlassian.net, with or without https://) -> Confluence base URL."""
    url = site.strip().rstrip("/")
    url = url if url.startswith(("http://", "https://")) else f"https://{url}"
    return url if url.endswith("/wiki") else url + "/wiki"


class Confluence:
    """Minimal Confluence Cloud REST client (content API v1, email + API token)."""

    def __init__(self, site: str, space: str, user: str, token: str, urlopen=urllib.request.urlopen):
        self.url, self.space, self.urlopen = site_url(site), space, urlopen
        self.auth = "Basic " + base64.b64encode(f"{user}:{token}".encode()).decode()

    def call(self, method: str, path: str, payload: dict | list | None = None) -> dict:
        req = urllib.request.Request(self.url + path, method=method,
                                     data=json.dumps(payload).encode() if payload is not None else None,
                                     headers={"Authorization": self.auth, "Accept": "application/json",
                                              "Content-Type": "application/json"})
        try:
            with self.urlopen(req) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:  # report the status, never the request headers
            raise PublishError(f"{method} {path.split('?')[0]}: HTTP {e.code}") from None

    def find(self, title: str) -> dict | None:
        query = urllib.parse.urlencode({"spaceKey": self.space, "title": title,
                                        "expand": "version,body.storage,metadata.labels"})
        results = self.call("GET", f"/rest/api/content?{query}").get("results", [])
        if not results:
            return None
        r = results[0]
        labels = [label["name"] for label in r.get("metadata", {}).get("labels", {}).get("results", [])]
        return {"id": r["id"], "version": r["version"]["number"], "body": r["body"]["storage"]["value"],
                "labels": labels}

    def _payload(self, title: str, parent_id: str | None, body: str) -> dict:
        payload = {"type": "page", "title": title, "space": {"key": self.space},
                   "body": {"storage": {"value": body, "representation": "storage"}}}
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]
        return payload

    def create(self, title: str, parent_id: str | None, body: str) -> str:
        return self.call("POST", "/rest/api/content", self._payload(title, parent_id, body))["id"]

    def update(self, page_id: str, version: int, title: str, parent_id: str | None, body: str) -> None:
        payload = self._payload(title, parent_id, body) | {"id": page_id, "version": {"number": version + 1}}
        self.call("PUT", f"/rest/api/content/{page_id}", payload)

    def add_labels(self, page_id: str, labels: list[str]) -> None:
        self.call("POST", f"/rest/api/content/{page_id}/label", [{"prefix": "global", "name": n} for n in labels])

    def remove_label(self, page_id: str, label: str) -> None:
        self.call("DELETE", f"/rest/api/content/{page_id}/label?" + urllib.parse.urlencode({"name": label}))


def sync_labels(client, page_id: str, current: list[str], wanted: list[str]) -> bool:
    """Add missing labels and remove outdated status labels; other labels are left alone."""
    missing = [n for n in wanted if n not in current]
    outdated = [n for n in current if n in STATUS_LABELS and n not in wanted]
    if missing:
        client.add_labels(page_id, missing)
    for name in outdated:
        client.remove_label(page_id, name)
    return bool(missing or outdated)


def publish(pages: list[Page], client, root_parent_id: str | None = None) -> list[tuple[str, str]]:
    """Create or update every page and its labels; return (action, title). Nothing is written if a page is foreign."""
    found = {p.title: client.find(p.title) for p in pages}
    foreign = [p.title for p in pages if found[p.title] and f"Generated from {p.source} " not in found[p.title]["body"]]
    if foreign:
        raise PublishError(f"not generated by this script, refusing to overwrite: {', '.join(foreign)}")
    ids, actions = {}, []
    for p in pages:
        parent_id = ids.get(p.parent) if p.parent else root_parent_id
        page = found[p.title]
        if page is None:
            ids[p.title] = client.create(p.title, parent_id, p.body)
            sync_labels(client, ids[p.title], [], p.labels)
            actions.append(("created", p.title))
            continue
        ids[p.title] = page["id"]
        relabeled = sync_labels(client, page["id"], page.get("labels", []), p.labels)
        if f"Fingerprint: {p.fingerprint}." not in page["body"]:
            client.update(page["id"], page["version"], p.title, parent_id, p.body)
            actions.append(("updated", p.title))
        else:
            actions.append(("labeled" if relabeled else "unchanged", p.title))
    return actions


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True).stdout.strip()


def previous_versions(tmp: Path, metadata: str):
    """previous(package) for collect_pages: checks out the package's last approved commit under tmp."""
    cache: dict[str, Version] = {}

    def previous(package: str) -> Version | None:
        commit = last_approved(package)
        if commit is None:
            return None
        if commit not in cache:
            dest = tmp / commit
            checkout(REPO_ROOT, commit, CHECKOUT_PATHS, dest)
            state = DocStatusFile.model_validate_json((dest / ROOT_SOURCE).read_text(encoding="utf-8"))
            cache[commit] = Version(dest, load_metadata(dest / metadata, root=dest), commit, state)
        return cache[commit]
    return previous


def main(argv: list[str] | None = None) -> int:
    load_dotenv(REPO_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--live", action="store_true", help="publish to Confluence instead of a dry run")
    ap.add_argument("--include-drafts", action="store_true", help="dry run only: also render unapproved docs")
    ap.add_argument("--out", default="build/confluence", help="dry-run output folder")
    ap.add_argument("--metadata", default=os.getenv("METADATA_DIR", "metadata"))
    args = ap.parse_args(argv)

    try:
        if args.live:
            if args.include_drafts:
                raise PublishError("--include-drafts is for dry runs; only approved docs go live")
            if os.getenv("PUBLISH_MODE", "rest") not in ("", "rest"):
                raise PublishError("this script publishes through the REST API; set PUBLISH_MODE=rest")
            missing = [name for name in LIVE_ENV if not os.getenv(name)]
            if missing:
                raise PublishError(f"set {', '.join(missing)} in .env (see .env.example)")
            if git("status", "--porcelain", "--", *GIT_PATHS):
                raise PublishError("uncommitted changes in " + ", ".join(GIT_PATHS) + "; publish only committed docs")
        state = DocStatusFile.model_validate_json((REPO_ROOT / ROOT_SOURCE).read_text(encoding="utf-8"))
        meta = load_metadata((REPO_ROOT / args.metadata).resolve())
        glossary = sorted(p.relative_to(REPO_ROOT).as_posix() for p in (REPO_ROOT / "glossary").glob("*.md"))
        with tempfile.TemporaryDirectory() as tmp:  # the previous versions are read while rendering
            pages, skipped = collect_pages(state, meta, git("rev-parse", "HEAD"), os.getenv("SOURCE_BASE_URL", ""),
                                           args.include_drafts, glossary,
                                           previous=previous_versions(Path(tmp), args.metadata))
        for line in skipped:
            print(f"skipped    {line}")
        for page in pages:
            if page.previous and page.parent == ROOT_TITLE:
                print(f"previous   {page.title}: not approved now; showing the version approved at "
                      f"{page.previous[:12]} ({page.status})")
        if args.live:
            client = Confluence(*(os.environ[name] for name in LIVE_ENV))
            for action, title in publish(pages, client, os.getenv("CONFLUENCE_PARENT_ID") or None):
                print(f"{action:<10} {title}")
        else:
            out = (REPO_ROOT / args.out).resolve()
            write_dry_run(pages, out)
            for page in pages:
                print(f"rendered   {page.title} ({page.status})")
            print(f"dry run: {len(pages)} pages written to {out}")
    except PublishError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
