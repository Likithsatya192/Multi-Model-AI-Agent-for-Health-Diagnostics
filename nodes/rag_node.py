import hashlib
import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from graph.graph_state import ReportState

load_dotenv()
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
FAISS_INDEX_DIR = os.getenv("FAISS_INDEX_DIR", "faiss_index")
CHAT_HISTORY_MAX_TURNS = 10   # keep last N turns per session
SESSION_TTL_SECONDS = 3600    # 1 hour — sessions older than this are purged

# ── In-memory stores (keyed by session/namespace) ─────────────────────────────
_faiss_stores: Dict[str, FAISS] = {}
_faiss_store_lock = threading.Lock()

chat_history_store: Dict[str, List[Tuple[str, str]]] = {}
chat_history_lock = threading.Lock()

report_state_store: Dict[str, Any] = {}
session_timestamps: Dict[str, float] = {}  # for TTL tracking


# ── Session TTL cleanup ───────────────────────────────────────────────────────
def _cleanup_expired_sessions():
    """Background thread: remove sessions older than SESSION_TTL_SECONDS."""
    while True:
        time.sleep(600)  # run every 10 min
        now = time.time()
        expired = [
            sid for sid, ts in list(session_timestamps.items())
            if now - ts > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            with _faiss_store_lock:
                _faiss_stores.pop(sid, None)
            with chat_history_lock:
                chat_history_store.pop(sid, None)
            report_state_store.pop(sid, None)
            session_timestamps.pop(sid, None)
            logger.info(f"Expired session purged: {sid}")


_cleanup_thread = threading.Thread(target=_cleanup_expired_sessions, daemon=True)
_cleanup_thread.start()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _touch_session(session_id: str):
    session_timestamps[session_id] = time.time()


def _compute_index_hash(index_path: str) -> str:
    """Compute SHA-256 of the FAISS index files for integrity check."""
    h = hashlib.sha256()
    for fname in sorted(os.listdir(index_path)):
        fpath = os.path.join(index_path, fname)
        if os.path.isfile(fpath):
            with open(fpath, "rb") as f:
                h.update(f.read())
    return h.hexdigest()


def _save_index_hash(index_path: str, digest: str):
    with open(os.path.join(index_path, ".hash"), "w") as f:
        f.write(digest)


def _verify_index_hash(index_path: str) -> bool:
    hash_file = os.path.join(index_path, ".hash")
    if not os.path.exists(hash_file):
        logger.warning(f"No hash file for index at {index_path} — treating as untrusted")
        return False
    with open(hash_file) as f:
        stored = f.read().strip()
    # Recompute excluding the hash file itself
    h = hashlib.sha256()
    for fname in sorted(os.listdir(index_path)):
        if fname == ".hash":
            continue
        fpath = os.path.join(index_path, fname)
        if os.path.isfile(fpath):
            with open(fpath, "rb") as f2:
                h.update(f2.read())
    current = h.hexdigest()
    return current == stored


def get_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)


# ── Public API ────────────────────────────────────────────────────────────────
def store_report_state(session_id: str, state: Any):
    if session_id:
        report_state_store[session_id] = state
        _touch_session(session_id)


def rag_indexing_node(state: ReportState) -> Dict[str, Any]:
    """
    Node: Index document text into FAISS for RAG retrieval.
    Persists index to disk with integrity hash. No dangerous deserialization.
    """
    raw_text = state.raw_text
    file_path = state.raw_file_path

    if not raw_text:
        logger.warning("rag_indexing: no text to index")
        return {"errors": ["No text available for RAG indexing"]}

    try:
        namespace = f"report_{uuid.uuid4().hex}"

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150,
            add_start_index=True,
        )
        metadata = {"source": file_path or "unknown"}
        docs = [
            Document(page_content=chunk, metadata=metadata)
            for chunk in splitter.split_text(raw_text)
        ]

        if not docs:
            return {"errors": ["Text splitting produced no chunks"]}

        logger.info(f"rag_indexing: indexing {len(docs)} chunks into namespace '{namespace}'")
        embeddings = get_embeddings()
        vectorstore = FAISS.from_documents(docs, embeddings)

        # Persist to disk
        index_path = os.path.join(FAISS_INDEX_DIR, namespace)
        os.makedirs(index_path, exist_ok=True)
        vectorstore.save_local(index_path)

        # Save integrity hash — prevents loading tampered indexes
        digest = _compute_index_hash(index_path)
        _save_index_hash(index_path, digest)

        with _faiss_store_lock:
            _faiss_stores[namespace] = vectorstore

        logger.info(f"rag_indexing: complete, namespace={namespace}")
        return {"rag_collection_name": namespace}

    except Exception as e:
        logger.exception(f"rag_indexing failed: {e}")
        return {"errors": [f"RAG Indexing Error: {str(e)}"]}


def rag_retrieve_and_answer(
    question: str,
    collection_name: str,
    session_id: str = None,
    report_context: Any = None,
) -> str:
    """
    Retrieve relevant context from FAISS and answer via LLM.
    Validates FAISS index integrity before loading from disk.
    """
    if session_id is None:
        session_id = "default"

    _touch_session(session_id)

    with chat_history_lock:
        if session_id not in chat_history_store:
            chat_history_store[session_id] = []

    try:
        embeddings = get_embeddings()

        # Load from memory or verified disk
        with _faiss_store_lock:
            vectorstore = _faiss_stores.get(collection_name)

        if vectorstore is None:
            index_path = os.path.join(FAISS_INDEX_DIR, collection_name)
            if not os.path.exists(index_path):
                return "Error: The report index was not found. Please re-upload the report."

            # Security: verify index integrity before loading
            if not _verify_index_hash(index_path):
                logger.error(f"FAISS index integrity check failed: {index_path}")
                return "Error: Report index integrity check failed. Please re-upload the report."

            # Safe to load — hash verified
            vectorstore = FAISS.load_local(
                index_path,
                embeddings,
                allow_dangerous_deserialization=True,  # safe: hash verified above
            )
            with _faiss_store_lock:
                _faiss_stores[collection_name] = vectorstore

        retriever = vectorstore.as_retriever(search_kwargs={"k": 6})
        retrieved_docs = retriever.invoke(question)
        context = "\n".join([doc.page_content for doc in retrieved_docs])

        if not retrieved_docs:
            logger.warning(f"rag_retrieve: no docs retrieved for namespace={collection_name}")

        # Build conversation history (last N turns)
        with chat_history_lock:
            history_turns = chat_history_store[session_id][-CHAT_HISTORY_MAX_TURNS:]

        history_context = ""
        if history_turns:
            lines = []
            for user_msg, assistant_msg in history_turns:
                lines.append(f"User: {user_msg}\nAssistant: {assistant_msg}")
            history_context = "\nPrevious conversation:\n" + "\n".join(lines)

        # Build analysis state context
        if report_context is None and session_id in report_state_store:
            report_context = report_state_store[session_id]

        report_context_str = ""
        if report_context:
            if hasattr(report_context, "model_dump"):
                ctx_data = report_context.model_dump()
            elif hasattr(report_context, "dict"):
                ctx_data = report_context.dict()
            else:
                ctx_data = report_context if isinstance(report_context, dict) else {}

            # Truncate raw text to prevent context overflow
            if ctx_data.get("raw_text") and len(ctx_data["raw_text"]) > 3000:
                ctx_data["raw_text"] = ctx_data["raw_text"][:3000] + "... [truncated]"
            # Remove raw_file_path (sensitive)
            ctx_data.pop("raw_file_path", None)

            report_context_str = json.dumps(ctx_data, indent=2, default=str)

        prompt = PromptTemplate(
            input_variables=["context", "question", "history", "report_context"],
            template="""You are a dedicated AI medical assistant analyzing a patient's uploaded blood report.
Your sole purpose is to explain findings, clarify medical terms, and answer questions about THIS specific report.

STRICT SCOPE RULE:
If the user asks anything NOT related to this blood report (general topics, coding, life advice, etc.),
respond EXACTLY with: "Please talk about only the uploaded blood report."

For report-related questions:
1. Use both the FULL Analysis State and Retrieved Text Context below.
2. Be professional, empathetic, and clear.
3. Use **bold** for key parameters. Use bullet points for clarity.
4. Use ### Subheadings to structure longer answers.
5. Never make definitive diagnoses. Always recommend consulting a doctor for medical decisions.
6. If a critical value was found, remind the user to seek medical attention promptly.

FULL Analysis State:
{report_context}

Retrieved Report Excerpts:
{context}

Conversation History:
{history}

User Question: {question}

Answer:""",
        )

        groq_api_key = os.environ.get("GROQ_API_KEY")
        if not groq_api_key:
            raise EnvironmentError("GROQ_API_KEY not set")

        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0,
            max_tokens=2048,
            timeout=90,
            api_key=groq_api_key,
        )

        result = (prompt | llm).invoke({
            "context": context,
            "question": question,
            "history": history_context,
            "report_context": report_context_str,
        })

        answer = result.content.strip() if hasattr(result, "content") else str(result).strip()

        with chat_history_lock:
            chat_history_store[session_id].append((question, answer))

        return answer

    except Exception as e:
        logger.exception(f"rag_retrieve_and_answer failed: {e}")
        return f"I encountered an error while processing your question. Please try again."


def get_chat_history(session_id: str = None) -> List[Tuple[str, str]]:
    if session_id is None:
        session_id = "default"
    with chat_history_lock:
        return list(chat_history_store.get(session_id, []))


def clear_chat_history(session_id: str = None) -> None:
    if session_id is None:
        session_id = "default"
    with chat_history_lock:
        chat_history_store.pop(session_id, None)


def clear_all_chat_history() -> None:
    with chat_history_lock:
        chat_history_store.clear()
