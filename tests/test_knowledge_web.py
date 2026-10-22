import sqlite3

from fastapi.testclient import TestClient

import knowledge_web


def test_edit_only_site_keeps_article_edits_and_rejects_other_operations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    scripts = tmp_path / "static" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "existing.md").write_text("# Original\n", encoding="utf-8")
    database = tmp_path / "data" / "knowledge.db"
    monkeypatch.setattr(knowledge_web.db, "DB_PATH", str(database))
    monkeypatch.setattr(knowledge_web, "ORIGIN", "https://example.com")
    with sqlite3.connect(database) as conn:
        conn.execute("""
            CREATE TABLE articles (
                id TEXT PRIMARY KEY, title TEXT, summary TEXT, article_md_path TEXT,
                tags TEXT, word_count INTEGER, created_at TEXT, source_type TEXT
            )
        """)
        conn.executemany(
            "INSERT INTO articles (id,title,summary,article_md_path,tags,created_at) VALUES (?,?,?,?,?,?)",
            [
                ("one", "Original", "Summary", "/static/scripts/existing.md", "[]", "2026-01-01"),
                ("two", "Fallback", "Summary", None, "[]", "2026-01-02"),
                ("bad", "Bad path", "", "/static/scripts/../../secret.md", "[]", "2026-01-03"),
            ],
        )

    headers = {"Origin": "https://example.com"}
    with TestClient(knowledge_web.app) as client:
        assert client.get("/api/articles").json()["articles"][0]["id"] == "bad"
        content = client.get("/api/articles/one/content").json()
        assert content["content"] == "# Original\n"
        denied = client.put("/api/articles/one/content", json={"content": "edited", "revision": content["revision"]})
        assert denied.status_code == 403
        saved = client.put("/api/articles/one/content", headers=headers, json={"content": "# Edited\n", "revision": content["revision"]})
        assert saved.status_code == 200
        assert (scripts / "existing.md").read_text(encoding="utf-8") == "# Edited\n"
        stale = client.put("/api/articles/one/content", headers=headers, json={"content": "stale", "revision": content["revision"]})
        assert stale.status_code == 409
        assert (scripts / "existing.md").read_text(encoding="utf-8") == "# Edited\n"
        assert client.patch("/api/articles/one", headers=headers, json={"title": "New title", "tags": ["读书", "思考"]}).status_code == 200
        updated = client.get("/api/articles/one").json()
        assert updated["title"] == "New title"
        assert updated["tags"] == '["读书", "思考"]'
        assert client.get("/api/tags").json()["tags"] == [{"tag": "读书", "count": 1}, {"tag": "思考", "count": 1}]
        assert [item["id"] for item in client.get("/api/articles?tag=读书").json()["articles"]] == ["one"]

        fallback = client.get("/api/articles/two/content").json()
        assert fallback["fallback"] is True
        created = client.put("/api/articles/two/content", headers=headers, json={"content": "# Created", "revision": fallback["revision"]})
        assert created.status_code == 200
        assert client.get("/api/articles/two/content").json()["content"] == "# Created"
        assert client.get("/api/articles/bad/content").status_code == 404
        assert client.post("/api/chat", headers=headers, json={}).status_code == 404
        assert client.post("/generate/url", headers=headers, json={}).status_code == 404
        assert client.get("/brain/api/articles").status_code == 404
