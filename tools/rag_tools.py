"""
RAG (Retrieval-Augmented Generation) tools.
Indexes chat history and research reports from AI Data/My AI/ into ChromaDB.
Uses Mistral Embed API for embeddings.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain.tools import tool

load_dotenv()

_CHROMA_DIR = Path(__file__).parent.parent / "data" / "chroma_db"
_COLLECTION_NAME = "cassanoval_memory"


def _get_vault_dir() -> Path:
    vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    return Path(vault) if vault else Path(__file__).parent.parent / "AI Data" / "My AI"


def _get_embeddings():
    from langchain_mistralai import MistralAIEmbeddings
    return MistralAIEmbeddings(
        model="mistral-embed",
        api_key=os.getenv("MISTRAL_API_KEY"),
    )


def _get_vectorstore(embeddings=None):
    from langchain_chroma import Chroma
    _CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=_COLLECTION_NAME,
        embedding_function=embeddings or _get_embeddings(),
        persist_directory=str(_CHROMA_DIR),
    )


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            # Prefer breaking at paragraph, then sentence boundary
            para = text.rfind("\n\n", start, end)
            if para > start + chunk_size // 2:
                end = para
            else:
                sent = text.rfind(". ", start, end)
                if sent > start + chunk_size // 2:
                    end = sent + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap

    return chunks


def _scan_documents() -> list[dict]:
    vault = _get_vault_dir()
    docs = []

    # (directory, source_type, recurse)
    targets = [
        (vault, "chat_history", False),
        (vault / "Ferry Agent", "research", True),
        (vault / "Social Scraper", "social_trends", True),
        (vault / "Da Vinci Agent", "ideas", True),
        (vault / "Linus Agent", "code_notes", True),
        (vault / "Mansa Agent", "finance", True),
        (vault / "Lavoiser Agent", "nutrition", True),
    ]

    for scan_dir, source_type, recurse in targets:
        if not scan_dir.exists():
            continue
        files = list(scan_dir.rglob("*.md")) if recurse else list(scan_dir.glob("*.md"))
        for filepath in files:
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore").strip()
                if len(content) < 50:
                    continue
                docs.append({
                    "content": content,
                    "source": str(filepath),
                    "source_type": source_type,
                    "filename": filepath.name,
                })
            except Exception:
                continue

    return docs


@tool
def index_documents(force_reindex: bool = False) -> str:
    """
    Index all chat history and research reports into RAG memory (ChromaDB).
    Run this after new data has been added — after a research session, after scraping, etc.
    Args:
        force_reindex: If True, wipes and rebuilds the entire index. Default False = incremental (only new files).
    """
    try:
        embeddings = _get_embeddings()
        vs = _get_vectorstore(embeddings)

        if force_reindex:
            vs.delete_collection()
            vs = _get_vectorstore(embeddings)

        docs = _scan_documents()
        if not docs:
            return "Tidak ada dokumen ditemukan di vault untuk diindeks."

        # Collect already-indexed sources to skip
        existing_sources: set[str] = set()
        if not force_reindex:
            try:
                existing = vs.get(include=["metadatas"])
                for m in existing.get("metadatas", []):
                    if m and m.get("source"):
                        existing_sources.add(m["source"])
            except Exception:
                pass

        texts, metadatas = [], []
        new_files = 0

        for doc in docs:
            if doc["source"] in existing_sources:
                continue
            chunks = _chunk_text(doc["content"])
            for i, chunk in enumerate(chunks):
                texts.append(chunk)
                metadatas.append({
                    "source": doc["source"],
                    "source_type": doc["source_type"],
                    "filename": doc["filename"],
                    "chunk_index": i,
                })
            new_files += 1

        if not texts:
            return f"Index sudah up-to-date. {len(docs)} file sudah terindeks, tidak ada yang baru."

        vs.add_texts(texts=texts, metadatas=metadatas)

        return (
            f"RAG index diperbarui:\n"
            f"  File baru: {new_files} | Chunk baru: {len(texts)}\n"
            f"  Total dokumen dipindai: {len(docs)}\n"
            f"  Tersimpan di: {_CHROMA_DIR}"
        )
    except Exception as e:
        return f"[index_documents error] {e}"


@tool
def search_memory(query: str, top_k: int = 5) -> str:
    """
    Search RAG memory — past conversations, research reports, financial summaries,
    code notes, nutrition logs, and idea files — for content relevant to the query.
    Use this before answering questions that might have been discussed or researched before.
    Args:
        query: Question, topic, or keyword phrase to search for.
        top_k: Number of results to return (default 5).
    """
    try:
        vs = _get_vectorstore()

        try:
            count = vs._collection.count()
        except Exception:
            count = 0

        if count == 0:
            return (
                "RAG memory belum diindeks. Panggil index_documents() terlebih dahulu "
                "untuk mengindeks riwayat chat dan laporan riset."
            )

        results = vs.similarity_search_with_relevance_scores(query, k=top_k)
        if not results:
            return f"Tidak ada hasil relevan untuk: '{query}'"

        parts = [f"Hasil pencarian memori untuk: '{query}'\n"]
        for i, (doc, score) in enumerate(results, 1):
            meta = doc.metadata
            parts.append(
                f"[{i}] [{meta.get('source_type', '?')}] {meta.get('filename', '?')} "
                f"(relevansi: {score:.0%})\n"
                f"{doc.page_content[:600]}\n"
            )

        return "\n".join(parts)
    except Exception as e:
        return f"[search_memory error] {e}"


RAG_TOOLS = [index_documents, search_memory]
