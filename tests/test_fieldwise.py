import io
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from fieldwise.retrieval import Index, read_document
from fieldwise.answers import answer_question, validate_citations
from fieldwise.app import create_app
from fieldwise.evaluate import evaluate

@pytest.fixture
def index(tmp_path):
    value=Index(tmp_path/"test.sqlite3")
    value.ingest("pump.md",["Pump Alpha amber indicator means inlet strainer inspection is due. Ticket ALPHA-STRAINER."])
    return value

def test_retrieval_and_citations(index):
    response=answer_question(index,"What does the Pump Alpha amber indicator mean?")
    assert response["status"]=="answered"
    assert response["sources"][0]["name"]=="pump.md"
    assert "[S1]" in response["answer"]
    assert len(response["sources"][0]["version"])==64

def test_unknown_question_abstains(index):
    assert answer_question(index,"What is the capital city of Argentina?")["status"]=="insufficient_evidence"

def test_empty_and_fts_syntax_are_safe(index):
    assert index.retrieve('" * OR NEAR()')==[]
    assert index.retrieve("and the is")==[]
    assert index.documents()[0]["name"]=="pump.md"

def test_dedup_and_replacement(index):
    original=index.documents()[0]["version"]
    result=index.ingest("pump.md",["Pump Alpha amber indicator means inlet strainer inspection is due. Ticket ALPHA-STRAINER."])
    assert result["unchanged"] and len(index.documents())==1
    index.ingest("pump.md",["Replacement manual: violet beacon means training calibration."])
    assert index.retrieve("amber strainer")==[]
    assert index.retrieve("violet calibration")
    assert index.documents()[0]["version"]!=original

def test_empty_replacement_does_not_destroy_index(index):
    with pytest.raises(ValueError):
        index.ingest("pump.md",["   "])
    assert index.retrieve("amber strainer")

@pytest.mark.parametrize("text",["No citation at all.","Claim [S99].","Claim [S1] and [S2]."])
def test_invalid_citations_rejected(text):
    assert not validate_citations(text,[{"citation_id":"S1"}])

def test_model_unknown_citation_fails_closed(index,monkeypatch):
    monkeypatch.setattr("fieldwise.answers.openai_answer",lambda *_:"Unsupported instruction [S99].")
    assert answer_question(index,"Pump Alpha amber indicator","openai")["status"]=="citation_check_failed"

def test_api_payload_and_response_parsing(index,monkeypatch):
    captured={}
    monkeypatch.setenv("OPENAI_API_KEY","unit-test-placeholder")
    monkeypatch.setenv("OPENAI_MODEL","unit-test-model")
    def fake(request,timeout):
        captured.update(json.loads(request.data))
        return io.BytesIO(json.dumps({"status":"completed","output":[
            {"type":"message","content":[{"type":"output_text","text":"Inspect the strainer [S1]."}]}]}).encode())
    monkeypatch.setattr("fieldwise.answers.urlopen",fake)
    response=answer_question(index,"Pump Alpha amber indicator","openai")
    assert response["status"]=="answered"
    assert captured["store"] is False and captured["model"]=="unit-test-model"
    assert "untrusted_sources" in json.loads(captured["input"])

def test_text_extraction_and_unsupported_input(tmp_path):
    p=tmp_path/"sample.md";p.write_text("Synthetic text")
    assert read_document(p)==["Synthetic text"]
    p=tmp_path/"bad.exe";p.write_bytes(b"data")
    with pytest.raises(ValueError):
        read_document(p)

def test_http_boundaries_and_sources(tmp_path):
    with TestClient(create_app(tmp_path/"api.sqlite3")) as client:
        assert client.get("/").status_code==200
        assert client.post("/api/documents",json={"name":"pump.md","text":"Pump Alpha amber indicator means strainer inspection."}).status_code==200
        response=client.post("/api/ask",json={"question":"Pump Alpha amber indicator"}).json()
        assert response["sources"][0]["name"]=="pump.md"
        assert client.post("/api/ask",json={"question":"x"*1001}).status_code==422
        assert client.post("/api/ask",content="{}").status_code==415
        assert client.post("/api/ask",json={"question":"Pump Alpha"},headers={"origin":"https://attacker.invalid"}).status_code==403
        assert client.post("/api/documents",json={"name":"a.md","text":"x"*1_000_001}).status_code==413
        assert client.get("/",headers={"host":"attacker.invalid"}).status_code==400

def test_synthetic_evaluation():
    root=Path(__file__).parents[1]
    report=evaluate(root/"sample_docs",root/"evals/questions.json")
    assert report["passed"]==report["cases"]==8
