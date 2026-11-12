class Retriever:
    def __init__(self, indexer):
        self.indexer = indexer

    def retrieve(self, token, repository, query, file=None, symbol=None, signature=None, k=3, captured_snapshot=None, hybrid=None):
        # Authenticate before opening storage, loading manifests, or embedding input.
        scope = self.indexer.permissions.authorize(token, repository)
        if file is not None:
            scope.resolve(file)
        if not query.strip() or len(query.encode()) > 1800 or not 1 <= k <= 10:
            raise ValueError("Query must be nonempty, <=1800 bytes; k must be 1..10")
        with self.indexer.lock:
            self.indexer.open_storage(scope)
            manifest = (self.indexer.catalog.snapshot(scope, captured_snapshot) if captured_snapshot
                        else self.indexer.catalog.current(scope))
            if manifest is None:
                raise ValueError("No active index for the authorized path scope")
            if manifest["embedding"] != self.indexer.embedder.identity:
                raise ValueError("Active index embedding identity mismatch; rebuild with the configured model")
            snapshot = manifest["snapshot"]
            allowed = [p for p in manifest["source"] if scope.allows(p)]
            targets = [c for c in manifest["chunks"] if c["file"] in allowed
                       and (file is None or c["file"] == file)
                       and (symbol is None or c["symbol"] == symbol)
                       and (signature is None or c["signature"] == signature)] if file or symbol else []
            matches = {(c["file"], c["symbol"], c["signature"]) for c in targets if c["symbol"]}
            if symbol and len(matches) > 1:
                return {"retrieval_status": "ambiguous", "snapshot": snapshot,
                        "matches": [dict(file=f, symbol=s, signature=g) for f, s, g in sorted(matches)]}
            if (symbol or file) and not targets:
                return {"retrieval_status": "not_found", "snapshot": snapshot,
                        "target": [], "related_code": [], "rules": []}
            enabled = self.indexer.code_aware if hybrid is None else hybrid
            if enabled:
                from app.retrieval.code_retrieval import target_facts, code_query, rank, RANKING
                query = code_query(query, targets, target_facts(manifest, targets))
            vector = self.indexer.embedder.encode([query])[0]
            active = self.indexer.catalog.current(scope)
            if captured_snapshot and active["snapshot"] != snapshot:
                # Old vectors may have been cleaned after re-index. Retain exact
                # captured target/rules; never search a newer source generation.
                related, rules = [], manifest["rules"][:k]
            else:
                related = self.indexer.store.query(self.indexer.store.code, vector, repository, snapshot, min(10, k * 3) if enabled else k, allowed)
                rules = self.indexer.store.query(self.indexer.store.rules, vector, repository, snapshot, k)
            seen = {c["chunk_id"] for c in targets}
            related = [c for c in related if c["chunk_id"] not in seen]
            limitations = []
            if enabled:
                related, limitations = rank(manifest, targets, related, query, allowed)
                related = related[:k]
                targets = [dict(c, retrieval_reasons=['REQUIRED_TARGET']) for c in targets]
                rules = [dict(r, retrieval_reasons=['ENGINEERING_RULE']) for r in rules]
            return {"retrieval_status": "ok", "repository": repository, "snapshot": snapshot,
                    "target": targets, "related_code": related, "rules": rules,
                    "limitations": ["Retrieved evidence only; no defect assessment",
                                     "Target may span multiple bounded chunks"] + limitations,
                    "ranking": RANKING if enabled else 'existing-vector',
                    "parser_status": manifest["parser_status"]}
