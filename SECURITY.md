# Security and deployment scope

This is a local, single-user reference app. The server binds 127.0.0.1. Do not expose it directly to the public internet or load confidential company documents into the demo.

Default mode is offline. OpenAI mode transmits the question and selected document passages to api.openai.com using a server-side key. Configure that mode only for data approved for that destination. The key is neither logged nor returned to the browser.

Documents are untrusted inputs. The browser accepts text/Markdown only. PDF extraction is a CLI extra using a native parser: process untrusted PDFs in a sandboxed worker with CPU/memory/time limits before production use. Text limits are checked after extraction and do not sandbox the parser.

Source instructions can be malicious. The prompt treats retrieved text as evidence, not instructions; citation checks only validate identifiers. They do not establish factual correctness or prevent every prompt injection.

The sample manuals describe fictional equipment. Their invented values are not maintenance or safety instructions.
