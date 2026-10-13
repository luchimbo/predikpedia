"""Public research uses the existing private, user-scoped SQLite store."""

import json
from uuid import uuid4

from app.domain.research_models import ResearchDocument, ResearchProject, stamp
from app.storage.evidence_repository import canonical


class ResearchRepository:
    def __init__(self, evidence_store):
        self.store = evidence_store
        with self.store.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS research_projects (
                    id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS research_documents (
                    id TEXT PRIMARY KEY, url TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS research_snapshots (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, payload TEXT NOT NULL);
            """)

    def save(self, project):
        with self.store.connect() as db:
            db.execute("INSERT OR REPLACE INTO research_projects VALUES (?, ?, ?)",
                       (project.id, stamp(), canonical(project.to_dict())))

    def get(self, project_id):
        with self.store.connect() as db:
            row = db.execute("SELECT payload FROM research_projects WHERE id=?", (project_id,)).fetchone()
        return ResearchProject.from_dict(json.loads(row[0])) if row else None

    def list_projects(self):
        with self.store.connect() as db:
            rows = db.execute("SELECT payload FROM research_projects ORDER BY updated_at DESC").fetchall()
        return [ResearchProject.from_dict(json.loads(row[0])) for row in rows]

    def save_document(self, document):
        with self.store.connect() as db:
            # Document IDs contain the content hash; snapshots retain the exact version read.
            db.execute("INSERT OR IGNORE INTO research_documents VALUES (?, ?, ?)",
                       (document.id, document.url, canonical(document.to_dict())))

    def documents(self, ids=None):
        with self.store.connect() as db:
            rows = db.execute("SELECT payload FROM research_documents").fetchall()
        wanted = set(ids) if ids is not None else None
        return [ResearchDocument(**json.loads(row[0])) for row in rows
                if wanted is None or json.loads(row[0])["id"] in wanted]

    def snapshot(self, project, *, extra=None):
        snapshot_id = uuid4().hex
        payload = {"project": project.to_dict(), "documents": [d.to_dict() for d in self.documents(project.document_ids)],
                   **(extra or {})}
        with self.store.connect() as db:
            db.execute("INSERT INTO research_snapshots VALUES (?, ?, ?, ?)",
                       (snapshot_id, project.id, stamp(), canonical(payload)))
        return snapshot_id

    def get_snapshot(self, snapshot_id):
        with self.store.connect() as db:
            row = db.execute("SELECT payload FROM research_snapshots WHERE id=?", (snapshot_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def history(self, project_id):
        with self.store.connect() as db:
            rows = db.execute("SELECT id FROM research_snapshots WHERE project_id=? ORDER BY created_at", (project_id,)).fetchall()
        return [row[0] for row in rows]
