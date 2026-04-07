from typing import List, Any, Dict, Tuple
from graph.graph_state import ReportState
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

# Chat history storage (in-memory)
chat_history_store: Dict[str, List[Tuple[str, str]]] = {}

# Embedding Model
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# In-memory storage for analysis reports
report_state_store: Dict[str, Any] = {}

# FAISS index directory
FAISS_INDEX_DIR = os.getenv("FAISS_INDEX_DIR", "faiss_index")

# In-memory FAISS store keyed by namespace (session/report id)
_faiss_stores: Dict[str, FAISS] = {}


def store_report_state(session_id: str, state: Any):
    """Stores the analysis report state for a session."""
    if session_id:
        report_state_store[session_id] = state

def get_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

def rag_indexing_node(state: ReportState) -> Dict[str, Any]:
    """
    Indexes the document content into a FAISS vector store.
    Each report gets a unique namespace stored in memory and optionally persisted to disk.
    """
    print("--- RAG INDEXING NODE (FAISS) ---")

    raw_text = state.raw_text
    file_path = state.raw_file_path

    if not raw_text:
        print("No text to index.")
        return {"errors": ["No text available for RAG indexing"]}

    try:
        # Generate a unique namespace for this session/report
        namespace = f"report_{uuid.uuid4().hex}"

        # Split text
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            add_start_index=True,
        )

        metadata = {"source": file_path if file_path else "unknown"}
        docs = [Document(page_content=text, metadata=metadata) for text in text_splitter.split_text(raw_text)]

        if not docs:
            print("No documents created from text splitter.")
            return {"errors": ["Text splitting failed"]}

        embeddings = get_embeddings()

        print(f"Indexing {len(docs)} chunks into FAISS namespace '{namespace}'...")

        vectorstore = FAISS.from_documents(docs, embeddings)

        # Persist to disk so the index survives across requests
        index_path = os.path.join(FAISS_INDEX_DIR, namespace)
        os.makedirs(index_path, exist_ok=True)
        vectorstore.save_local(index_path)

        # Also keep in memory for fast access in the same process
        _faiss_stores[namespace] = vectorstore

        print(f"Successfully indexed into FAISS namespace: {namespace}")

        return {"rag_collection_name": namespace}

    except Exception as e:
        print(f"Error in RAG node: {e}")
        return {"errors": [f"RAG Indexing Error: {str(e)}"]}


def rag_retrieve_and_answer(question: str, collection_name: str, session_id: str = None, report_context: Any = None) -> str:
    """
    Retrieves context from the FAISS index and generates an answer via Groq LLM.
    collection_name is the FAISS namespace (subdirectory under FAISS_INDEX_DIR).
    """
    from langchain_groq import ChatGroq
    from langchain_core.prompts import PromptTemplate
    import json

    if session_id is None:
        session_id = "default"

    if session_id not in chat_history_store:
        chat_history_store[session_id] = []

    try:
        embeddings = get_embeddings()

        # Load from memory or disk
        if collection_name in _faiss_stores:
            vectorstore = _faiss_stores[collection_name]
        else:
            index_path = os.path.join(FAISS_INDEX_DIR, collection_name)
            if not os.path.exists(index_path):
                return "Error: The report index was not found. Please re-upload the report."
            vectorstore = FAISS.load_local(
                index_path,
                embeddings,
                allow_dangerous_deserialization=True,
            )
            _faiss_stores[collection_name] = vectorstore

        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

        retrieved_docs = retriever.invoke(question)

        if not retrieved_docs:
            print("Warning: No documents retrieved from FAISS index.")

        context = "\n".join([doc.page_content for doc in retrieved_docs])

        # Build chat history context
        history_context = ""
        if chat_history_store[session_id]:
            history_context = "\nPrevious conversation:\n"
            for user_msg, assistant_msg in chat_history_store[session_id][-5:]:
                history_context += f"User: {user_msg}\nAssistant: {assistant_msg}\n"

        # Build analysis report context
        if report_context is None and session_id in report_state_store:
            report_context = report_state_store[session_id]

        report_context_str = ""
        if report_context:
            if hasattr(report_context, 'model_dump'):
                ctx_data = report_context.model_dump()
            elif hasattr(report_context, 'dict'):
                ctx_data = report_context.dict()
            else:
                ctx_data = report_context if isinstance(report_context, dict) else {}

            if 'raw_text' in ctx_data and ctx_data['raw_text'] and len(ctx_data['raw_text']) > 5000:
                ctx_data['raw_text'] = ctx_data['raw_text'][:5000] + "... (truncated in context)"

            report_context_str = json.dumps(ctx_data, indent=2, default=str)

        prompt = PromptTemplate(
            input_variables=["context", "question", "history", "report_context"],
            template="""You are a dedicated AI medical assistant analyzing a specific patient's uploaded blood report.
Your goal is to explain the report findings, clarify medical terms found in the report, and answer questions BASED STRICTLY on the provided context.

CRITICAL INSTRUCTION:
If the user asks a question that is NOT related to the uploaded medical report, or asks about general topics, coding, life advice, or anything outside the scope of this specific medical analysis, you MUST respond with EXACTLY this phrase:
"Please talk about only the uploaded blood report."

If the question is relevant to the report:
1. Synthesize information from the 'FULL Analysis State' (which contains the deep analysis, patterns, and recommendations) and the 'Retrieved Text Context' (raw text from the report).
2. Format your response professionally, similar to ChatGPT:
   - Use `### Subheadings` to structure your answer.
   - Use bullet points (`-`) for clarity.
   - Use **bold** text for key medical parameters or findings.
   - Keep the tone helpful, professional, and empathetic.

FULL Analysis State (Synthesis, Patterns, Recommendations):
{report_context}

Retrieved Text Context (Raw Report Excerpts):
{context}

Conversation History:
{history}

User Question: {question}

Answer:"""
        )

        chain = prompt | llm

        result = chain.invoke({
            "context": context,
            "question": question,
            "history": history_context,
            "report_context": report_context_str
        })

        answer = result.content.strip() if hasattr(result, 'content') else str(result).strip()

        chat_history_store[session_id].append((question, answer))

        return answer

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error responding to chat: {str(e)}"


def get_chat_history(session_id: str = None) -> List[Tuple[str, str]]:
    if session_id is None:
        session_id = "default"
    return chat_history_store.get(session_id, [])

def clear_chat_history(session_id: str = None) -> None:
    if session_id is None:
        session_id = "default"
    if session_id in chat_history_store:
        chat_history_store[session_id] = []

def clear_all_chat_history() -> None:
    global chat_history_store
    chat_history_store = {}
