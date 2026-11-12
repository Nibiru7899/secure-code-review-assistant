from pathlib import Path

import chromadb
from chromadb.config import Settings


class VectorStore:
    def __init__(self, directory):
        self.client = chromadb.PersistentClient(path=str(Path(directory).resolve()),
                                                settings=Settings(anonymized_telemetry=False))
        self.code = self.client.get_or_create_collection("repository_code", embedding_function=None,
            configuration={"hnsw": {"space": "cosine", "batch_size": 1, "sync_threshold": 1}})
        self.rules = self.client.get_or_create_collection("engineering_rules", embedding_function=None,
            configuration={"hnsw": {"space": "cosine", "batch_size": 1, "sync_threshold": 1}})
        # Chroma 1.0.20 can lose a filtered reader for buffered tiny collections.
        # Persist even one-vector batches, also for existing pilot collections.
        for collection in (self.code, self.rules):
            collection.modify(configuration={"hnsw": {"batch_size": 1, "sync_threshold": 1}})

    @staticmethod
    def scope_filter(repository, snapshot):
        return {"$and": [{"repository": repository}, {"snapshot": snapshot}]}

    def stage(self, code, code_vectors, rules, rule_vectors):
        for collection, records, vectors in [(self.code, code, code_vectors), (self.rules, rules, rule_vectors)]:
            for start in range(0, len(records), 100):
                batch = records[start:start + 100]
                collection.upsert(ids=[c["chunk_id"] for c in batch],
                                  documents=[c["text"] for c in batch],
                                  metadatas=[{k: v for k, v in c.items() if k != "text"} for c in batch],
                                  embeddings=vectors[start:start + len(batch)])

    def delete(self, repository, snapshot):
        where = self.scope_filter(repository, snapshot)
        self.code.delete(where=where)
        self.rules.delete(where=where)

    def close(self):
        # Chroma 1.0.20 has no public close. Stop its pinned local system only
        # after all clients using this directory have finished, releasing Windows
        # handles without resetting or deleting persisted content.
        systems = self.client._identifier_to_system
        system = systems.pop(self.client._identifier, None)
        if system is not None:
            system.stop()

    def query(self, collection, vector, repository, snapshot, k, files=None):
        where = self.scope_filter(repository, snapshot)
        if files is not None:
            if not files:
                return []
            where["$and"].append({"file": {"$in": files}})
        result = collection.query(query_embeddings=[vector], where=where, n_results=k,
                                  include=["metadatas", "documents", "distances"])
        return [dict(metadata, text=document, distance=distance)
                for metadata, document, distance in zip(result["metadatas"][0],
                                                        result["documents"][0], result["distances"][0])]
