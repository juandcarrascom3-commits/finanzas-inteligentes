"""Research persistence foundation (Research R1A).

ResearchStore is a dedicated, minimal persistence boundary for Research
knowledge items. It composes an existing ``DatabaseManager`` for database
connections and migration lifecycle; it never owns database paths, PRAGMAs,
or migrations, and it never modifies ``database/db_manager.py``.

Preview/ingest orchestration, audit events, and API concerns live in the
Research service (R1B/R1C) — not here.
"""

import hashlib
import json
from contextlib import closing
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

Identity = Union[Tuple[str, str], Sequence[str], Dict[str, Any]]


class ResearchStore:
    """Read/upsert access to ``research_items`` in one SQLite transaction."""

    def __init__(self, db):
        # Composition: the DatabaseManager owns the path, PRAGMAs, and the
        # migration lifecycle that creates ``research_items`` (008).
        self._db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def get_by_identities(self, identities: Sequence[Identity]) -> List[Dict[str, Any]]:
        """Return persisted R0-compatible items for the given identities.

        Each identity is a ``(source_id, external_ref)`` pair (sequence or
        mapping). Results are ordered by ``id`` for determinism.
        """
        with closing(self._db.get_connection()) as conn:
            rows = self._fetch_rows(conn, identities)
        return [self._row_to_item(row) for row in rows]

    def list_items(
        self,
        source_id: Optional[str] = None,
        epistemic: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return persisted items with deterministic ordering.

        Order: ``published_at DESC`` (SQLite places NULLs last) with ``id ASC``
        as the tie-breaker.
        """
        clauses: List[str] = []
        params: List[Any] = []
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if epistemic is not None:
            clauses.append("epistemic = ?")
            params.append(epistemic)
        sql = "SELECT * FROM research_items"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY published_at DESC, id ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        with closing(self._db.get_connection()) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_item(row) for row in rows]

    def relevant_state_fingerprint(self, identities: Sequence[Identity]) -> str:
        """sha256 over the sorted ``id|content_hash`` of rows in scope.

        Scoped: only rows matching the supplied identities contribute, so
        unrelated Research rows never invalidate a fingerprint. Deterministic
        and clock-free (no system time participates).
        """
        with closing(self._db.get_connection()) as conn:
            rows = self._fetch_rows(conn, identities)
        material = sorted(f"{row['id']}|{row['content_hash']}" for row in rows)
        return hashlib.sha256("\n".join(material).encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def upsert_items_atomic(self, items: List[Dict[str, Any]]) -> Dict[str, int]:
        """Insert/update normalized items in one logical transaction.

        All accepted writes commit together; any failure rolls back the whole
        batch (zero partial Research writes). Unchanged items (same identity,
        same ``content_hash``) are a true no-op: no UPDATE runs, so
        ``created_at``/``updated_at`` stay untouched.
        """
        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        with closing(self._db.get_connection()) as conn:
            try:
                seen: Dict[Tuple[str, str], str] = {}
                for item in items:
                    pair = (item["source_id"], item["external_ref"])
                    content_hash = item["content_hash"]
                    prior_hash = seen.get(pair)
                    if prior_hash is not None and prior_hash != content_hash:
                        raise ValueError("RESEARCH_BATCH_IDENTITY_CONFLICT")
                    seen[pair] = content_hash
                    if not item.get("id"):
                        raise ValueError("RESEARCH_ID_REQUIRED")
                    existing = conn.execute(
                        "SELECT id, content_hash FROM research_items "
                        "WHERE source_id = ? AND external_ref = ?",
                        pair,
                    ).fetchone()
                    if existing is not None:
                        if existing["content_hash"] == content_hash:
                            counts["unchanged"] += 1
                            continue
                        conn.execute(self._update_sql, self._payload(item, id=existing["id"]))
                        counts["updated"] += 1
                    else:
                        conn.execute(self._insert_sql, self._payload(item))
                        counts["inserted"] += 1
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return counts

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    _insert_sql = """
        INSERT INTO research_items (
            id, source_id, external_ref, title, url, summary, published_at,
            fetched_at, content_hash, epistemic, entity_tickers,
            normalization_status, provider, ingestion_method, language, reasons,
            external_ref_derived
        ) VALUES (
            :id, :source_id, :external_ref, :title, :url, :summary, :published_at,
            :fetched_at, :content_hash, :epistemic, :entity_tickers,
            :normalization_status, :provider, :ingestion_method, :language, :reasons,
            :external_ref_derived
        )
    """

    _update_sql = """
        UPDATE research_items SET
            title = :title, url = :url, summary = :summary,
            published_at = :published_at, fetched_at = :fetched_at,
            content_hash = :content_hash, epistemic = :epistemic,
            entity_tickers = :entity_tickers,
            normalization_status = :normalization_status,
            provider = :provider, ingestion_method = :ingestion_method,
            language = :language, reasons = :reasons,
            external_ref_derived = :external_ref_derived,
            updated_at = datetime('now')
        WHERE id = :id
    """

    @staticmethod
    def _identity_pair(identity: Identity) -> Tuple[str, str]:
        if isinstance(identity, dict):
            return str(identity["source_id"]), str(identity["external_ref"])
        source_id, external_ref = identity
        return str(source_id), str(external_ref)

    @classmethod
    def _fetch_rows(cls, conn, identities: Sequence[Identity]):
        pairs = [cls._identity_pair(identity) for identity in identities]
        if not pairs:
            return []
        placeholders = " OR ".join(
            "(source_id = ? AND external_ref = ?)" for _ in pairs
        )
        params = [value for pair in pairs for value in pair]
        return conn.execute(
            f"SELECT * FROM research_items WHERE {placeholders} ORDER BY id",
            params,
        ).fetchall()

    @staticmethod
    def _payload(item: Dict[str, Any], id: Optional[str] = None) -> Dict[str, Any]:
        # Lifecycle timestamps come from column defaults / datetime('now');
        # body/content and raw provider payloads are never persisted.
        return {
            "id": id if id is not None else item["id"],
            "source_id": item["source_id"],
            "external_ref": item["external_ref"],
            "title": item["title"],
            "url": item.get("url"),
            "summary": item.get("summary"),
            "published_at": item.get("published_at"),
            "fetched_at": item["fetched_at"],
            "content_hash": item["content_hash"],
            "epistemic": item["epistemic"],
            "entity_tickers": json.dumps(
                item.get("entity_tickers") or [], ensure_ascii=False
            ),
            "normalization_status": item["normalization_status"],
            "provider": item.get("provider"),
            "ingestion_method": item.get("ingestion_method"),
            "language": item.get("language"),
            "reasons": (
                json.dumps(item["reasons"], ensure_ascii=False)
                if item.get("reasons")
                else None
            ),
            "external_ref_derived": 1 if item.get("external_ref_derived") else 0,
        }

    @staticmethod
    def _row_to_item(row) -> Dict[str, Any]:
        """Reconstruct the exact R0 item contract from persisted fields only.

        ``provenance`` is rebuilt deterministically from stored columns —
        never invented — and optional keys stay absent when their column is
        NULL, mirroring ``normalize_research_item`` output.
        """
        item: Dict[str, Any] = {
            "id": row["id"],
            "source_id": row["source_id"],
            "external_ref": row["external_ref"],
            "title": row["title"],
            "url": row["url"],
            "published_at": row["published_at"],
            "fetched_at": row["fetched_at"],
            "content_hash": row["content_hash"],
            "epistemic": row["epistemic"],
            "entity_tickers": json.loads(row["entity_tickers"]),
            "normalization_status": row["normalization_status"],
            "provenance": {
                "source_id": row["source_id"],
                "external_ref": row["external_ref"],
                "url": row["url"],
                "published_at": row["published_at"],
                "fetched_at": row["fetched_at"],
                "content_hash": row["content_hash"],
            },
        }
        if row["summary"] is not None:
            item["summary"] = row["summary"]
        if row["provider"] is not None:
            item["provider"] = row["provider"]
            item["provenance"]["provider"] = row["provider"]
        if row["ingestion_method"] is not None:
            item["ingestion_method"] = row["ingestion_method"]
            item["provenance"]["ingestion_method"] = row["ingestion_method"]
        if row["language"] is not None:
            item["language"] = row["language"]
        if row["reasons"] is not None:
            item["reasons"] = json.loads(row["reasons"])
        if row["external_ref_derived"]:
            item["external_ref_derived"] = True
        return item
