import os
import re
import sys
import chromadb
from chromadb.utils import embedding_functions

RUNBOOKS_DIR = os.path.join(os.path.dirname(__file__), "runbooks")
DB_PATH = os.path.join(os.path.dirname(__file__), ".chroma_db")
COLLECTION_NAME = "runbooks"


def _get_collection(client: chromadb.Client):
    ef = embedding_functions.DefaultEmbeddingFunction()
    return client.get_or_create_collection(COLLECTION_NAME, embedding_function=ef)


def _chunk_markdown(text: str, source: str) -> list[dict]:
    """Split on H2/H3 headers so each chunk has semantic meaning.
    Falling back to paragraph splits if the doc has no headers."""
    chunks = re.split(r"\n(?=#{2,3} )", text)
    if len(chunks) <= 1:
        chunks = [p.strip() for p in text.split("\n\n") if p.strip()]

    results = []
    for i, chunk in enumerate(chunks):
        if len(chunk) < 40:  # skip stubs like lone header lines
            continue
        results.append({
            "id": f"{source}::{i}",
            "text": chunk.strip(),
            "source": source,
        })
    return results


def index_runbooks(force: bool = False) -> chromadb.Client:
    if not os.path.isdir(RUNBOOKS_DIR):
        print(f"\033[1;31mError:\033[0m Runbooks directory not found at '{RUNBOOKS_DIR}'.")
        print("Create it and add .md files to get runbook context in your summaries.")
        sys.exit(1)

    db = chromadb.PersistentClient(path=DB_PATH)
    collection = _get_collection(db)

    md_files = [f for f in os.listdir(RUNBOOKS_DIR) if f.endswith(".md")]
    if not md_files:
        print("\033[1;33mWarning:\033[0m No .md files found in runbooks/. Continuing without context.")
        return db

    # Only re-index if forced or the collection is empty — avoids re-embedding on every run
    if collection.count() > 0 and not force:
        return db

    print(f"  Indexing {len(md_files)} runbook(s)...")
    all_ids, all_texts, all_metas = [], [], []

    for fname in md_files:
        fpath = os.path.join(RUNBOOKS_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        for chunk in _chunk_markdown(content, fname):
            all_ids.append(chunk["id"])
            all_texts.append(chunk["text"])
            all_metas.append({"source": chunk["source"]})

    if all_ids:
        collection.upsert(ids=all_ids, documents=all_texts, metadatas=all_metas)

    return db


def query_runbooks(db: chromadb.Client, error_text: str, n_results: int = 2) -> list[str]:
    collection = _get_collection(db)
    if collection.count() == 0:
        return []

    results = collection.query(query_texts=[error_text], n_results=min(n_results, collection.count()))
    return results["documents"][0] if results["documents"] else []
