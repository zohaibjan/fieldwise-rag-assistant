import argparse
import json
from pathlib import Path
from .retrieval import Index, read_document
from .answers import answer_question

def main():
    parser=argparse.ArgumentParser(description="Local document retrieval with inspectable citations")
    parser.add_argument("--db",type=Path,default=Path("var/fieldwise.sqlite3"))
    commands=parser.add_subparsers(dest="command",required=True)
    ingest=commands.add_parser("ingest")
    ingest.add_argument("paths",type=Path,nargs="+")
    ask=commands.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--provider",choices=["extractive","openai"],default="extractive")
    serve=commands.add_parser("serve")
    serve.add_argument("--port",type=int,default=8001)
    args=parser.parse_args()
    if args.command=="serve":
        import uvicorn
        from .app import create_app
        uvicorn.run(create_app(args.db),host="127.0.0.1",port=args.port,access_log=False)
        return
    index=Index(args.db)
    if args.command=="ingest":
        for path in args.paths:
            print(json.dumps(index.ingest(path.name,read_document(path)),indent=2))
    elif args.command=="ask":
        print(json.dumps(answer_question(index,args.question,args.provider),indent=2))

if __name__=="__main__":
    main()
