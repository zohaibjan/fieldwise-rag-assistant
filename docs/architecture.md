# Architecture and review boundaries

**Local first:** SQLite holds document names, extracted text chunks, page numbers and SHA-256 content versions. The default extractive responder returns passages with citation IDs. No cloud model or remote embedding database is needed.

**Version replacement:** A document identity is derived from its basename. Re-ingestion with identical page text is a no-op; changed text deletes old chunks and inserts replacements in a single SQLite transaction. Keep source files separately when historical retention is required: this prototype stores the current searchable version only.

**Retrieval:** Questions are reduced to bounded word tokens and quoted before building an FTS5 OR query. BM25 ranks candidate chunks. A lexical-coverage threshold removes weak matches. This is a simple, inspectable baseline; it is not semantic similarity, calibrated confidence or a reranker.

**Generation:** The optional Responses API adapter receives the question plus selected passages as untrusted data. Instructions require citations and prohibit following document instructions. The response must complete and reference known source IDs. A citation-ID check cannot establish that every claim is supported, so responses still require review.

**HTTP boundary:** Local Host and same-origin checks, JSON-only mutations, a streamed 1 MB request cap, bounded fields, four concurrent work slots and generic provider errors. The frontend uses textContent rather than rendering model/document HTML.

**Production gap:** No multi-user authentication, document-level ACLs, durable audit log, malware isolation, background indexing, retention lifecycle, observability stack or high-availability service. Uploaded text is visible to the single local workbench user. A production RAG deployment needs these controls plus real corpus evaluation.
