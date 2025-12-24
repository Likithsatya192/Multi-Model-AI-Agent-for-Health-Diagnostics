from typing import List, Any, Dict, Tuple
from graph.graph_state import ReportState
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

# Chat history storage (in-memory, consider using a database for production)
chat_history_store: Dict[str, List[Tuple[str, str]]] = {}

# Initialize embeddings globally to avoid reloading overhead if possible, 
# or lazy load inside the functions.
# Using a popular free Hugging Face model.
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# In-memory storage for analysis reports (keyed by session_id)
# in persistent production, use Redis or Database
report_state_store: Dict[str, Any] = {}

def store_report_state(session_id: str, state: Any):
    """Stores the analysis report state for a session."""
    if session_id:
        report_state_store[session_id] = state

def get_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

def get_qdrant_client():
    # Check for Qdrant Cloud credentials
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    if qdrant_url and qdrant_api_key:
        print(f"Using Qdrant Cloud: {qdrant_url}")
        return QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=60)
    else:
        # Fallback to local
        print("Using Local Qdrant (Disk)")
        return QdrantClient(path="./qdrant_data")

def rag_indexing_node(state: ReportState) -> Dict[str, Any]:
    """
    Indexes the document content into Qdrant.
    """
    print("--- RAG INDEXING NODE ---")
    
    raw_text = state.raw_text
    file_path = state.raw_file_path
    
    if not raw_text:
        print("No text to index.")
        return {"errors": ["No text available for RAG indexing"]}

    try:
        # Generate a unique collection name for this session/report
        # In a real app, you might use a user_id or session_id
        collection_name = f"report_{uuid.uuid4().hex}"
        
        # Split text
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            add_start_index=True,
        )
        
        # If we have a file path, we might want to store it in metadata
        metadata = {"source": file_path if file_path else "unknown"}
        
        docs = [Document(page_content=text, metadata=metadata) for text in text_splitter.split_text(raw_text)]
        
        if not docs:
            print("No documents created from text splitter.")
            return {"errors": ["Text splitting failed"]}

        # Initialize Qdrant
        client = get_qdrant_client()
        embeddings = get_embeddings()
        
        if not client.collection_exists(collection_name):
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            
        vector_store = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=embeddings,
        )
        
        vector_store.add_documents(documents=docs)
        
        print(f"Indexed {len(docs)} chunks into collection {collection_name}")
        
        return {"rag_collection_name": collection_name}
        
    except Exception as e:
        print(f"Error in RAG node: {e}")
        return {"errors": [f"RAG Indexing Error: {str(e)}"]}

def rag_retrieve_and_answer(question: str, collection_name: str, session_id: str = None, report_context: Any = None) -> str:
    """
    Retrieves context and generates an answer using an LLM with chat history.
    This function is called by the API, not the graph.
    """
    from langchain_groq import ChatGroq
    from langchain_core.prompts import PromptTemplate
    import json
    
    if session_id is None:
        session_id = "default"
    
    # Initialize chat history for this session if not exists
    if session_id not in chat_history_store:
        chat_history_store[session_id] = []
    
    try:
        client = get_qdrant_client()
        embeddings = get_embeddings()
        
        # Ensure collection exists before querying to avoid errors
        if not client.collection_exists(collection_name):
             return "Error: The document collection was not found. Please upload the report again."

        vector_store = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=embeddings,
        )
        
        retriever = vector_store.as_retriever(search_kwargs={"k": 5})
        
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
        
        # Retrieve relevant documents
        retrieved_docs = retriever.invoke(question)
        context = "\n".join([doc.page_content for doc in retrieved_docs])
        
        # Build chat history context
        history_context = ""
        if chat_history_store[session_id]:
            history_context = "\nPrevious conversation:\n"
            for user_msg, assistant_msg in chat_history_store[session_id][-5:]:  # Keep last 5 exchanges
                history_context += f"User: {user_msg}\nAssistant: {assistant_msg}\n"

        # Build Analysis Report Context (FULL STATE)
        # Check if context was passed explicitly, otherwise try to retrieve from store
        if report_context is None and session_id in report_state_store:
            report_context = report_state_store[session_id]

        report_context_str = ""
        if report_context:
            # Convert Pydantic or dict to dict
            if hasattr(report_context, 'model_dump'):
                ctx_data = report_context.model_dump()
            elif hasattr(report_context, 'dict'):
                ctx_data = report_context.dict()
            else:
                ctx_data = report_context if isinstance(report_context, dict) else {}
            
            # Remove potentially redundant huge raw text if we rely on vector db,
            # but user asked for "full state", so we keep everything unless it hits token limits.
            # We'll truncate raw_text if it's excessively large to avoid prompt errors, 
            # assuming vector store handles the granularity.
            if 'raw_text' in ctx_data and ctx_data['raw_text'] and len(ctx_data['raw_text']) > 5000:
                 ctx_data['raw_text'] = ctx_data['raw_text'][:5000] + "... (truncated in context, see retrieved docs)"

            report_context_str = json.dumps(ctx_data, indent=2, default=str)
        
        # Create prompt template
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
        
        # Create LCEL chain
        chain = prompt | llm
        
        # Generate answer
        result = chain.invoke({
            "context": context,
            "question": question,
            "history": history_context,
            "report_context": report_context_str
        })
        
        # Result from ChatModel is an AIMessage object
        answer = result.content.strip() if hasattr(result, 'content') else str(result).strip()
        
        # Store this exchange in history
        chat_history_store[session_id].append((question, answer))
        
        return answer
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error responding to chat: {str(e)}"


def get_chat_history(session_id: str = None) -> List[Tuple[str, str]]:
    """
    Retrieve chat history for a specific session.
    """
    if session_id is None:
        session_id = "default"
    return chat_history_store.get(session_id, [])


def clear_chat_history(session_id: str = None) -> None:
    """
    Clear chat history for a specific session.
    """
    if session_id is None:
        session_id = "default"
    if session_id in chat_history_store:
        chat_history_store[session_id] = []


def clear_all_chat_history() -> None:
    """
    Clear all chat history across all sessions.
    """
    global chat_history_store
    chat_history_store = {}
