from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

import chromadb
import jieba

VECTOR_DIMENSION = 128


def embed_text(text: str) -> list[float]:
    vector = [0.0] * VECTOR_DIMENSION
    tokens = [token.lower() for token in jieba.cut_for_search(text) if token.strip()]
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % VECTOR_DIMENSION
        sign = 1.0 if digest[4] % 2 else -1.0
        weight = 1.0 + min(len(token), 8) / 8
        vector[index] += sign * weight
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class ChromaVectorStore:
    backend_name = "chroma"

    def __init__(self, path: Path):
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.path),
            settings=chromadb.Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name="vitak_chunks",
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        chunk_id: str,
        text: str,
        metadata: dict[str, Any],
    ) -> None:
        self.collection.upsert(
            ids=[chunk_id],
            documents=[text],
            embeddings=[embed_text(text)],
            metadatas=[metadata],
        )

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if self.collection.count() == 0:
            return []
        result = self.collection.query(
            query_embeddings=[embed_text(query)],
            n_results=min(limit, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        output = []
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for index, chunk_id in enumerate(ids):
            distance = float(distances[index]) if index < len(distances) else 1.0
            output.append(
                {
                    "chunk_id": chunk_id,
                    "text": documents[index] if index < len(documents) else "",
                    "metadata": metadatas[index] if index < len(metadatas) else {},
                    "score": max(0.0, 1.0 - distance),
                }
            )
        return output

    def upsert_many(
        self,
        items: list[tuple[str, str, dict[str, Any]]],
    ) -> None:
        if not items:
            return
        self.collection.upsert(
            ids=[item[0] for item in items],
            documents=[item[1] for item in items],
            embeddings=[embed_text(item[1]) for item in items],
            metadatas=[item[2] for item in items],
        )

    def count(self) -> int:
        return int(self.collection.count())

    def reset(self) -> None:
        try:
            self.client.delete_collection("vitak_chunks")
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name="vitak_chunks",
            metadata={"hnsw:space": "cosine"},
        )
