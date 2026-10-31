"""publish_confluence.py: page selection, markdown conversion and the live publish logic, without a network.

The fixture package is the one from test_validate_doc.py; the live tests use an in-memory Confluence.
"""

import io
import json
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import pytest

import scripts.publish_confluence as pc
from scripts.extract_metadata import REPO_ROOT, extract
from scripts.models import DocState, DocStatusEntry, DocStatusFile
from scripts.validate_doc import Metadata, load_metadata

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "validate"
SOURCES = ["tests/fixtures/validate/legacy/packages/pkg_demo.pks", "tests/fixtures/validate/legacy/packages/pkg_demo.pkb"]
COMMIT = "0123456789abcdef0123456789abcdef01234567"
BASE = "https://git.example/repo/blob"


@pytest.fixture(scope="module")
def meta():
    return Metadata(*extract(FIXTURES / "legacy"))


def state(status=DocState.APPROVED, source_hash=None):
    entry = DocStatusEntry(package="PKG_DEMO", doc_path="tests/fixtures/validate/pkg_demo.md", source_files=SOURCES,
                           source_hash=source_hash or pc.source_hash(SOURCES, REPO_ROOT), status=status,
                           updated_at=datetime(2026, 10, 31, tzinfo=timezone.utc), validation_passed=True)
    return DocStatusFile(entries={"PKG_DEMO": entry})


def well_formed(body):
    ET.fromstring(f'<root xmlns:ac="urn:ac" xmlns:ri="urn:ri">{body}</root>')


def test_draft_is_not_published(meta):
    pages, skipped = pc.collect_pages(state(DocState.DRAFT), meta, COMMIT, BASE)
    assert [p.title for p in pages] == [pc.ROOT_TITLE]
    assert skipped == ["PKG_DEMO: status draft, publishing needs approved"]


def test_approved_doc_is_converted(meta):
    pages, skipped = pc.collect_pages(state(), meta, COMMIT, BASE)
    assert skipped == []
    root, page = pages
    assert (page.title, page.parent, page.status) == ("Package PKG_DEMO", pc.ROOT_TITLE, DocState.APPROVED)
    assert "PKG_DEMO" in root.body
    well_formed(page.body)
    assert page.body.startswith('<ac:structured-macro ac:name="info">')
    assert "Generated from tests/fixtures/validate/pkg_demo.md at commit 0123456789ab." in page.body
    assert "<h1>" not in page.body  # the title is the page title
    # citations link to the cited lines of the file at the commit
    assert (f'<a href="{BASE}/{COMMIT}/tests/fixtures/validate/legacy/packages/pkg_demo.pks#L2">'
            "[PKG_DEMO(spec):2]</a>") in page.body
    # open questions become tasks
    assert page.body.count("<ac:task>") == 2


def test_changed_source_is_published_as_stale(meta):
    pages, _ = pc.collect_pages(state(source_hash="0" * 64), meta, COMMIT, BASE)
    assert pages[1].status == DocState.STALE
    assert pages[1].body.startswith('<ac:structured-macro ac:name="warning">')


def test_include_drafts_renders_a_preview(meta):
    pages, skipped = pc.collect_pages(state(DocState.DRAFT), meta, COMMIT, BASE, include_drafts=True)
    assert skipped == [] and pages[1].body.startswith('<ac:structured-macro ac:name="note">')


def test_inline_markup(meta):
    conv = pc.Converter(meta, {"docs/a.md": "Page A"}, COMMIT, "")
    out = conv.inline("**Bold** `x < y` [a](a.md), [b](b.md) [PKG_DEMO.GET_QTY:16] & more", pc.PurePosixPath("docs"))
    assert out.startswith("<strong>Bold</strong> <code>x &lt; y</code> ")
    assert '<ri:page ri:content-title="Page A" />' in out
    assert ", b " in out  # link to an unpublished doc keeps only its text
    assert "[PKG_DEMO.GET_QTY:16] &amp; more" in out  # no SOURCE_BASE_URL: citation stays text


def test_real_docs_render(tmp_path):
    meta = load_metadata(REPO_ROOT / "metadata")
    real = DocStatusFile.model_validate_json((REPO_ROOT / "state/doc-status.json").read_text(encoding="utf-8"))
    pages, _ = pc.collect_pages(real, meta, COMMIT, BASE, include_drafts=True, glossary=["glossary/conventions.md"])
    for page in pages:
        well_formed(page.body)
    by_title = {p.title: p for p in pages}
    assert by_title["UTIL_LOG.LOG_MSG"].parent == "Package UTIL_LOG"
    assert '<ri:page ri:content-title="Package UTIL_LOG" />' in by_title["UTIL_LOG.LOG_MSG"].body
    pc.write_dry_run(pages, tmp_path)
    manifest = json.loads((tmp_path / "pages.json").read_text(encoding="utf-8"))
    assert len(manifest) == len(pages) == len(list(tmp_path.glob("*.xhtml")))


class FakeConfluence:
    def __init__(self):
        self.pages, self.writes = {}, []

    def find(self, title):
        return self.pages.get(title)

    def create(self, title, parent_id, body):
        page_id = str(len(self.pages) + 1)
        self.pages[title] = {"id": page_id, "version": 1, "body": body, "parent": parent_id}
        self.writes.append(("create", title))
        return page_id

    def update(self, page_id, version, title, parent_id, body):
        self.pages[title] = {"id": page_id, "version": version + 1, "body": body, "parent": parent_id}
        self.writes.append(("update", title))


def test_publish_creates_skips_and_updates(meta):
    pages, _ = pc.collect_pages(state(), meta, COMMIT, BASE)
    fake = FakeConfluence()
    assert pc.publish(pages, fake) == [("created", pc.ROOT_TITLE), ("created", "Package PKG_DEMO")]
    assert fake.pages["Package PKG_DEMO"]["parent"] == fake.pages[pc.ROOT_TITLE]["id"]

    again, _ = pc.collect_pages(state(), meta, "f" * 40, BASE)  # new commit, same doc and source
    assert [a for a, _ in pc.publish(again, fake)] == ["unchanged", "unchanged"]

    stale, _ = pc.collect_pages(state(source_hash="0" * 64), meta, COMMIT, BASE)
    assert pc.publish(stale, fake)[1] == ("updated", "Package PKG_DEMO")


def test_publish_never_overwrites_a_foreign_page(meta):
    pages, _ = pc.collect_pages(state(), meta, COMMIT, BASE)
    fake = FakeConfluence()
    fake.pages["Package PKG_DEMO"] = {"id": "9", "version": 3, "body": "<p>written by hand</p>"}
    with pytest.raises(pc.PublishError, match="refusing to overwrite: Package PKG_DEMO"):
        pc.publish(pages, fake)
    assert fake.writes == []


def test_live_preconditions(monkeypatch, capsys):
    monkeypatch.setattr(pc, "load_dotenv", lambda *a, **k: None)  # never pick up a real .env here
    for name in pc.LIVE_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ATLASSIAN_TOKEN", "secret-token-value")
    assert pc.main(["--live", "--include-drafts"]) == 2
    assert "only approved docs go live" in capsys.readouterr().err
    monkeypatch.setenv("PUBLISH_MODE", "mcp")
    assert pc.main(["--live"]) == 2
    assert "set PUBLISH_MODE=rest" in capsys.readouterr().err
    monkeypatch.setenv("PUBLISH_MODE", "rest")
    assert pc.main(["--live"]) == 2
    err = capsys.readouterr().err
    assert "CONFLUENCE_SITE, CONFLUENCE_SPACE, ATLASSIAN_EMAIL" in err and "secret-token-value" not in err


def test_root_page_goes_under_parent_id(meta):
    pages, _ = pc.collect_pages(state(), meta, COMMIT, BASE)
    fake = FakeConfluence()
    pc.publish(pages, fake, root_parent_id="123")
    assert fake.pages[pc.ROOT_TITLE]["parent"] == "123"
    assert fake.pages["Package PKG_DEMO"]["parent"] == fake.pages[pc.ROOT_TITLE]["id"]


@pytest.mark.parametrize("site", ["yourname.atlassian.net", "https://yourname.atlassian.net/",
                                  "https://yourname.atlassian.net/wiki"])
def test_site_url(site):
    assert pc.site_url(site) == "https://yourname.atlassian.net/wiki"


def test_client_requests():
    sent = []

    def urlopen(req):
        sent.append(req)
        if req.get_method() == "PUT":
            raise urllib.error.HTTPError(req.full_url, 409, "Conflict", {}, None)
        return io.BytesIO(json.dumps({"id": "42", "results": []}).encode())

    client = pc.Confluence("wiki.example", "DOC", "bot@example.com", "secret-token-value", urlopen)
    assert client.find("Package PKG_DEMO") is None
    assert client.create("Package PKG_DEMO", "7", "<p>x</p>") == "42"
    with pytest.raises(pc.PublishError) as e:
        client.update("42", 1, "Package PKG_DEMO", "7", "<p>y</p>")
    assert "HTTP 409" in str(e.value) and "secret" not in str(e.value)

    get, post, put = sent
    assert get.full_url.startswith("https://wiki.example/wiki/rest/api/content?spaceKey=DOC&title=Package+PKG_DEMO")
    assert post.get_header("Authorization").startswith("Basic ")
    assert json.loads(post.data)["ancestors"] == [{"id": "7"}]
    assert json.loads(put.data)["version"] == {"number": 2}
