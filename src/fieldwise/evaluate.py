"""Evaluate synthetic retrieval and abstention, not production answer accuracy."""
import argparse
import json
import tempfile
from pathlib import Path
from .retrieval import Index,read_document

def evaluate(corpus: Path, cases: Path):
    with tempfile.TemporaryDirectory() as directory:
        index=Index(Path(directory)/"index.sqlite3")
        for path in sorted(corpus.glob("*.md")):
            index.ingest(path.name,read_document(path))
        rows=[]
        for case in json.loads(cases.read_text()):
            results=index.retrieve(case["question"],limit=3)
            names={r["name"] for r in results}
            passed=case["expected_document"] in names if case["expected_document"] else not results
            rows.append({**case,"retrieved_documents":sorted(names),"passed":passed})
    return {"scope":"Synthetic lexical-retrieval/abstention regression set",
            "cases":len(rows),"passed":sum(r["passed"] for r in rows),"results":rows}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--corpus",type=Path,default=Path("sample_docs"))
    parser.add_argument("--cases",type=Path,default=Path("evals/questions.json"))
    args=parser.parse_args()
    report=evaluate(args.corpus,args.cases)
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report["passed"]==report["cases"] else 1)

if __name__=="__main__":
    main()
