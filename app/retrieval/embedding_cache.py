"""Private scope-bound content cache; active snapshot membership stays separate."""
import hashlib
import json
import sqlite3
from contextlib import closing
from time import perf_counter


def encode_cached(indexer, scope, records):
    started = perf_counter()
    path = indexer.data_dir / 'embedding-cache.sqlite3'
    with closing(sqlite3.connect(path)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS embeddings (key TEXT PRIMARY KEY, vector TEXT NOT NULL)')
        keys = [hashlib.sha256(json.dumps([scope.repository, scope.key, indexer.embedder.identity, r['text']]).encode()).hexdigest() for r in records]
        cached = {key: row[0] for key in set(keys) if (row := db.execute('SELECT vector FROM embeddings WHERE key=?', (key,)).fetchone())}
        missing = list(dict.fromkeys(key for key in keys if key not in cached))
        texts = {key: record['text'] for key, record in zip(keys, records)}
        # Long functions remain complete source units. Their vector is only a
        # supplementary signature/identifier summary within embedding limits.
        from app.retrieval.code_retrieval import identifiers
        inputs = [texts[key] if len(texts[key].encode()) <= 1800 else
                  'Code identifiers: ' + ' '.join(sorted(identifiers(texts[key]))[:100]) for key in missing]
        vectors = indexer.embedder.encode(inputs) if inputs else []
        for key, vector in zip(missing, vectors):
            cached[key] = json.dumps(vector)
            db.execute('INSERT OR REPLACE INTO embeddings VALUES (?,?)', (key, cached[key]))
        if len(vectors) != len(missing):
            raise ValueError('Embedding batch length mismatch')
        db.commit()
    return [json.loads(cached[key]) for key in keys], {'computed': len(missing), 'reused': len(keys) - len(missing),
                                                      'seconds': round(perf_counter() - started, 4)}
