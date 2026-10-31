"""publish_confluence.py: page selection, markdown conversion and the live publish logic, without a network.

The fixture package is the one from test_validate_doc.py; the live tests use an in-memory Confluence.
"""

import io
import json
import subprocess
import urllib.error
import urllib.parse
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
    # first under the title: the AI generated and status lozenges, then the banner
    assert page.body.startswith('<p><ac:structured-macro ac:name="status">'
                                '<ac:parameter ac:name="title">AI GENERATED</ac:parameter>'
                                '<ac:parameter ac:name="colour">Purple</ac:parameter>')
    assert ('<ac:parameter ac:name="title">APPROVED</ac:parameter>'
            '<ac:parameter ac:name="colour">Green</ac:parameter>') in page.body
    assert page.body.split("</p>", 1)[1].startswith('<ac:structured-macro ac:name="info">')
    assert "APPROVED" not in root.body.split("</p>", 1)[0]
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
    assert '<ac:parameter ac:name="title">STALE</ac:parameter><ac:parameter ac:name="colour">Yellow</ac:parameter>' \
        in pages[1].body
    assert pages[1].body.split("</p>", 1)[1].startswith('<ac:structured-macro ac:name="warning">')


def test_unapproved_doc_keeps_its_last_approved_version(meta):
    old = "a" * 40
    previous = lambda name: pc.Version(REPO_ROOT, meta, old, state())  # noqa: E731 - approved at commit old
    pages, skipped = pc.collect_pages(state(DocState.DRAFT), meta, COMMIT, BASE, previous=previous)
    root, page = pages
    assert skipped == []
    assert (page.title, page.status, page.previous) == ("Package PKG_DEMO", DocState.APPROVED, old)
    banner_text = page.body.split("</p>", 1)[1]
    assert banner_text.startswith('<ac:structured-macro ac:name="note">') and pc.PREVIOUS_NOTE in banner_text
    assert "Generated from tests/fixtures/validate/pkg_demo.md at commit aaaaaaaaaaaa." in page.body
    assert f"{BASE}/{old}/tests/fixtures/validate/legacy/packages/pkg_demo.pks#L2" in page.body  # old commit's lines
    assert "approved, last approved version" in root.body

    # the source changed since that approval: stale, with both explanations
    stale = lambda name: pc.Version(REPO_ROOT, meta, old, state(source_hash="0" * 64))  # noqa: E731
    page = pc.collect_pages(state(DocState.DRAFT), meta, COMMIT, BASE, previous=stale)[0][1]
    assert page.status == DocState.STALE
    assert page.body.split("</p>", 1)[1].startswith('<ac:structured-macro ac:name="warning">')
    assert pc.PREVIOUS_NOTE in page.body and "The PL/SQL source changed" in page.body

    # never approved: skipped as before
    pages, skipped = pc.collect_pages(state(DocState.DRAFT), meta, COMMIT, BASE, previous=lambda name: None)
    assert len(pages) == 1 and skipped == ["PKG_DEMO: status draft, publishing needs approved"]


def test_last_approved_reads_the_state_history(tmp_path, git_env):
    def commit(status):
        (tmp_path / "state").mkdir(exist_ok=True)
        (tmp_path / pc.ROOT_SOURCE).write_text(state(status).model_dump_json(), encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", status], cwd=tmp_path, check=True)
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True,
                              text=True).stdout.strip()

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    commit(DocState.DRAFT)
    assert pc.last_approved("PKG_DEMO", tmp_path) is None
    approved = commit(DocState.APPROVED)
    commit(DocState.DRAFT)  # e.g. update-package after a source change
    assert pc.last_approved("PKG_DEMO", tmp_path) == approved
    assert pc.last_approved("OTHER", tmp_path) is None


def test_include_drafts_renders_a_preview(meta):
    pages, skipped = pc.collect_pages(state(DocState.DRAFT), meta, COMMIT, BASE, include_drafts=True)
    assert skipped == [] and pages[1].body.split("</p>", 1)[1].startswith('<ac:structured-macro ac:name="note">')


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

    def by_id(self, page_id):
        return next(p for p in self.pages.values() if p["id"] == page_id)

    def create(self, title, parent_id, body):
        page_id = str(len(self.pages) + 1)
        self.pages[title] = {"id": page_id, "version": 1, "body": body, "parent": parent_id, "labels": []}
        self.writes.append(("create", title))
        return page_id

    def update(self, page_id, version, title, parent_id, body):
        self.pages[title] |= {"version": version + 1, "body": body, "parent": parent_id}
        self.writes.append(("update", title))

    def add_labels(self, page_id, labels):
        self.by_id(page_id)["labels"] += labels

    def remove_label(self, page_id, label):
        self.by_id(page_id)["labels"].remove(label)


def test_publish_creates_skips_and_updates(meta):
    pages, _ = pc.collect_pages(state(), meta, COMMIT, BASE)
    fake = FakeConfluence()
    assert pc.publish(pages, fake) == [("created", pc.ROOT_TITLE), ("created", "Package PKG_DEMO")]
    assert fake.pages["Package PKG_DEMO"]["parent"] == fake.pages[pc.ROOT_TITLE]["id"]

    again, _ = pc.collect_pages(state(), meta, "f" * 40, BASE)  # new commit, same doc and source
    assert [a for a, _ in pc.publish(again, fake)] == ["unchanged", "unchanged"]

    stale, _ = pc.collect_pages(state(source_hash="0" * 64), meta, COMMIT, BASE)
    assert pc.publish(stale, fake)[1] == ("updated", "Package PKG_DEMO")


def test_labels_mark_ai_and_status(meta):
    pages, _ = pc.collect_pages(state(), meta, COMMIT, BASE)
    fake = FakeConfluence()
    pc.publish(pages, fake)
    assert fake.pages[pc.ROOT_TITLE]["labels"] == ["ai-generated"]
    assert fake.pages["Package PKG_DEMO"]["labels"] == ["ai-generated", "approved"]

    # a page published before labels existed gets them without a new version
    fake.pages["Package PKG_DEMO"]["labels"] = ["team-label"]
    assert pc.publish(pages, fake)[1] == ("labeled", "Package PKG_DEMO")
    assert fake.pages["Package PKG_DEMO"]["version"] == 1
    assert fake.pages["Package PKG_DEMO"]["labels"] == ["team-label", "ai-generated", "approved"]

    # the status label follows the status; labels added by people stay
    stale, _ = pc.collect_pages(state(source_hash="0" * 64), meta, COMMIT, BASE)
    pc.publish(stale, fake)
    assert fake.pages["Package PKG_DEMO"]["labels"] == ["team-label", "ai-generated", "stale"]


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
        if req.get_method() == "DELETE":
            return io.BytesIO(b"")  # 204 No Content
        return io.BytesIO(json.dumps({"id": "42", "results": []}).encode())

    client = pc.Confluence("wiki.example", "DOC", "bot@example.com", "secret-token-value", urlopen)
    assert client.find("Package PKG_DEMO") is None
    assert client.create("Package PKG_DEMO", "7", "<p>x</p>") == "42"
    with pytest.raises(pc.PublishError) as e:
        client.update("42", 1, "Package PKG_DEMO", "7", "<p>y</p>")
    assert "HTTP 409" in str(e.value) and "secret" not in str(e.value)
    client.add_labels("42", ["ai-generated", "approved"])
    client.remove_label("42", "stale")

    get, post, put, label, unlabel = sent
    assert get.full_url.startswith("https://wiki.example/wiki/rest/api/content?spaceKey=DOC&title=Package+PKG_DEMO")
    assert "metadata.labels" in urllib.parse.unquote(get.full_url)
    assert post.get_header("Authorization").startswith("Basic ")
    assert json.loads(post.data)["ancestors"] == [{"id": "7"}]
    assert json.loads(put.data)["version"] == {"number": 2}
    assert label.full_url.endswith("/rest/api/content/42/label")
    assert json.loads(label.data) == [{"prefix": "global", "name": "ai-generated"},
                                      {"prefix": "global", "name": "approved"}]
    assert (unlabel.get_method(), unlabel.full_url) == ("DELETE", "https://wiki.example/wiki/rest/api/content/42/label?name=stale")
