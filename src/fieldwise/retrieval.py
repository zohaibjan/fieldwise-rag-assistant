"""Transactional, versioned SQLite FTS5 retrieval; no external embedding service."""
from contextlib import contextmanager
import hashlib
import re
import sqlite3
from pathlib import Path

STOP = set("a an and are as at be by can do does for from how i in is it of on or should the to what when where which with you your".split())

def tokens(text: str) -> list[str]:
    return list(dict.fromkeys(t.casefold() for t in re.findall(r"[^\W_]+", text, re.UNICODE)
                              if len(t)>1 and t.casefold() not in STOP))[:40]

def chunks(text: str, size: int = 900, overlap: int = 120):
    text = text.strip()
    start = 0
    while start < len(text):
        end = min(start+size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start+size//2, end)
            if boundary > start:
                end = boundary
        piece = text[start:end].strip()
        if piece:
            yield piece
        if end == len(text):
            break
        start = max(start+1, end-overlap)

class Index:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents(
                    id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, version TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS chunks(
                    id INTEGER PRIMARY KEY, document_id TEXT NOT NULL,
                    page INTEGER NOT NULL, ordinal INTEGER NOT NULL, text TEXT NOT NULL);
                CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(text, chunk_id UNINDEXED);
                CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
            """)

    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path, timeout=10)
        db.row_factory=sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def ingest(self, name: str, pages: list[str]) -> dict:
        name = Path(name).name.strip()
        if not name or len(name)>180 or len(pages)>500:
            raise ValueError("Invalid document name or page count")
        if sum(len(p) for p in pages)>2_000_000:
            raise ValueError("Document text exceeds two million characters")
        pieces=[(page_no,ordinal,text) for page_no,page in enumerate(pages,1)
                for ordinal,text in enumerate(chunks(page))]
        if not pieces:
            raise ValueError("Document contains no extractable text")
        identity=hashlib.sha256(name.encode()).hexdigest()[:24]
        version=hashlib.sha256("\f".join(pages).encode()).hexdigest()
        with self.connection() as db:
            existing=db.execute("SELECT version FROM documents WHERE id=?",(identity,)).fetchone()
            if existing and existing["version"]==version:
                return {"document_id":identity,"version":version,"unchanged":True,"chunks":len(pieces)}
            if not existing and db.execute("SELECT count(*) FROM documents").fetchone()[0]>=100:
                raise ValueError("Local prototype document limit is 100")
            db.execute("DELETE FROM search WHERE chunk_id IN (SELECT id FROM chunks WHERE document_id=?)",(identity,))
            db.execute("DELETE FROM chunks WHERE document_id=?",(identity,))
            db.execute("INSERT INTO documents VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version",
                       (identity,name,version))
            for page,ordinal,text in pieces:
                cursor=db.execute("INSERT INTO chunks(document_id,page,ordinal,text) VALUES(?,?,?,?)",
                                  (identity,page,ordinal,text))
                db.execute("INSERT INTO search(text,chunk_id) VALUES(?,?)",(text,cursor.lastrowid))
        return {"document_id":identity,"version":version,"unchanged":False,"chunks":len(pieces)}

    def documents(self) -> list[dict]:
        with self.connection() as db:
            return [dict(row) for row in db.execute(
                "SELECT d.*,count(c.id) AS chunks FROM documents d JOIN chunks c ON c.document_id=d.id GROUP BY d.id ORDER BY d.name")]

    def retrieve(self, question: str, limit: int = 5) -> list[dict]:
        query_tokens=tokens(question)
        if not query_tokens:
            return []
        # Tokenization removes all FTS syntax; every token is still explicitly quoted.
        query=" OR ".join('"'+token.replace('"','""')+'"' for token in query_tokens)
        with self.connection() as db:
            rows=db.execute("""
                SELECT c.id,c.text,c.page,d.name,d.version,d.id AS document_id,bm25(search) AS score
                FROM search JOIN chunks c ON c.id=search.chunk_id
                JOIN documents d ON d.id=c.document_id
                WHERE search MATCH ? ORDER BY score LIMIT ?
            """,(query,min(max(limit,1),10))).fetchall()
        results=[]
        for row in rows:
            item=dict(row)
            present=set(tokens(item["text"]))
            coverage=len(set(query_tokens)&present)/len(query_tokens)
            if coverage>=0.35:
                item["coverage"]=round(coverage,3)
                item["citation_id"]="S"+str(len(results)+1)
                results.append(item)
        return results

def read_document(path: Path) -> list[str]:
    if path.stat().st_size>5*1024*1024:
        raise ValueError("Input file exceeds 5 MiB")
    if path.suffix.lower() in (".txt",".md"):
        return [path.read_text(encoding="utf-8")]
    if path.suffix.lower()==".pdf":
        import fitz
        with fitz.open(path) as document:
            if document.needs_pass or len(document)>500:
                raise ValueError("Encrypted or overlong PDF")
            return [page.get_text() for page in document]
    raise ValueError("Supported inputs: UTF-8 TXT/Markdown or text-based PDF; OCR is not included")
