"""Local, single-user document workbench. No credentials are sent to the browser."""
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .retrieval import Index
from .answers import answer_question

class Question(BaseModel):
    model_config=ConfigDict(extra="forbid")
    question: str=Field(min_length=3,max_length=1000)

class Document(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name: str=Field(min_length=1,max_length=180,pattern=r"^[\w .()-]+\.(txt|md)$")
    text: str=Field(min_length=1,max_length=200000)

async def body(request: Request, model):
    origin=request.headers.get("origin")
    if origin and urlsplit(origin).netloc!=request.headers.get("host"):
        raise HTTPException(403,"Cross-origin writes are disabled")
    if request.headers.get("content-type","").split(";")[0]!="application/json":
        raise HTTPException(415,"Send application/json")
    data=bytearray()
    async for block in request.stream():
        data.extend(block)
        if len(data)>1_000_000:
            raise HTTPException(413,"Request body exceeds 1 MB")
    try:
        return model.model_validate_json(data)
    except (ValidationError,ValueError):
        raise HTTPException(422,"Invalid request fields or field limits") from None

def create_app(database: Path | None = None, provider: str | None = None):
    index=Index(database or Path(os.getenv("FIELDWISE_DB","var/fieldwise.sqlite3")))
    provider=provider or os.getenv("FIELDWISE_PROVIDER","extractive")
    if provider not in ("extractive","openai"):
        raise ValueError("Invalid FIELDWISE_PROVIDER")
    app=FastAPI(title="FieldWise reference workbench")
    app.state.index=index
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=["127.0.0.1","localhost","[::1]","testserver"])
    static=Path(__file__).parent/"static"
    app.mount("/static",StaticFiles(directory=static),name="static")
    slots=asyncio.Semaphore(4)

    @app.get("/")
    def home():
        return FileResponse(static/"index.html")

    @app.get("/api/documents")
    def documents():
        return {"documents":index.documents(),"provider":provider}

    @app.post("/api/documents")
    async def ingest(request: Request):
        document=await body(request,Document)
        async with slots:
            try:
                return await asyncio.to_thread(index.ingest,document.name,[document.text])
            except ValueError as error:
                raise HTTPException(422,str(error)) from None

    @app.post("/api/ask")
    async def ask(request: Request):
        question=await body(request,Question)
        async with slots:
            try:
                return await asyncio.to_thread(answer_question,index,question.question,provider)
            except Exception:
                # Provider error bodies may contain request details; do not expose them.
                raise HTTPException(502,"Answer provider unavailable; check server configuration") from None

    @app.get("/health")
    def health():
        return {"status":"ok","documents":len(index.documents()),"provider":provider}
    return app
