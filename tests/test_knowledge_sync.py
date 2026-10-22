import copy
import sqlite3

from services import db, knowledge_document as document, knowledge_sync as sync


def test_sync_push_pull_and_conflict_preserves_both_sides(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    scripts = tmp_path / "static" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "one.md").write_text("# Original", encoding="utf-8")
    database = tmp_path / "data" / "knowledge.db"
    monkeypatch.setattr(db, "DB_PATH", str(database))
    with sqlite3.connect(database) as conn:
        conn.execute("""
            CREATE TABLE articles (
                id TEXT PRIMARY KEY, title TEXT, tags TEXT, summary TEXT,
                article_md_path TEXT, created_at TEXT, source_url TEXT,
                source_type TEXT, image_url TEXT, word_count INTEGER
            )
        """)
        conn.execute("""
            INSERT INTO articles (id, title, tags, article_md_path, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, ("one", "Original", "[]", "/static/scripts/one.md", "2026-01-01"))
    remote = {"one": copy.deepcopy(document.read_document("one"))}

    def fake_request(path, *, method="GET", body=None):
        if path == "/api/sync/manifest":
            return {"revisions": {article_id: item["revision"] for article_id, item in remote.items()}}
        if path == "/api/articles/one/document":
            if method == "GET":
                return copy.deepcopy(remote["one"])
            assert body["revision"] == remote["one"]["revision"]
            updated = {**remote["one"], **body}
            updated["revision"] = document.revision(updated["title"], updated["tags"], updated["content"])
            remote["one"] = updated
            return copy.deepcopy(updated)
        raise AssertionError(path)

    monkeypatch.setattr(sync, "_request", fake_request)
    assert sync.synchronize(apply=True)["same"] == ["one"]

    local = document.read_document("one")
    document.write_document("one", {**local, "content": "# Local edit"}, source="local")
    assert sync.synchronize(apply=True)["push"] == ["one"]
    assert remote["one"]["content"] == "# Local edit"

    remote["one"]["content"] = "# Server edit"
    remote["one"]["revision"] = document.revision("Original", [], "# Server edit")
    assert sync.synchronize(apply=True)["pull"] == ["one"]
    assert (scripts / "one.md").read_text(encoding="utf-8") == "# Server edit"

    remote["one"]["content"] = "# Fresh server edit"
    remote["one"]["revision"] = document.revision("Original", [], "# Fresh server edit")
    assert sync.read_canonical("one")["content"] == "# Fresh server edit"
    assert (scripts / "one.md").read_text(encoding="utf-8") == "# Fresh server edit"

    local = document.read_document("one")
    document.write_document("one", {**local, "content": "# Another local edit"}, source="local")
    remote["one"]["content"] = "# Another server edit"
    remote["one"]["revision"] = document.revision("Original", [], "# Another server edit")
    assert sync.synchronize(apply=True)["conflicts"] == ["one"]
    assert (scripts / "one.md").read_text(encoding="utf-8") == "# Another local edit"
    assert remote["one"]["content"] == "# Another server edit"
