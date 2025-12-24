from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import tempfile
from graph.run_pipeline import run_full_pipeline
from pydantic import BaseModel
from nodes.rag_node import rag_retrieve_and_answer, store_report_state

app = FastAPI()

# Allow CORS for React Frontend (usually runs on port 5173 or 3000)
# In production, replace ["*"] with your actual frontend domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    question: str
    collection_name: str
    session_id: str = None  # Added session_id, optional

@app.post("/analyze")
async def analyze_report(file: UploadFile = File(...), session_id: str = Form(None)):
    try:
        # Create a temp file to store the upload
        suffix = os.path.splitext(file.filename)[1]
        if not suffix:
            suffix = ".tmp"
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        
        # Run the existing pipeline
        # run_full_pipeline returns a GraphState object (pydantic model or similar)
        result = run_full_pipeline(tmp_path)
        
        # Store result in memory for RAG context if session_id provided
        if session_id:
            store_report_state(session_id, result)
        
        # Clean up temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass # Best effort cleanup

        # Convert result to a JSON-serializable format
        # Assuming result has attributes corresponding to your graph state
        response_data = {
            "risk_score": result.risk_assessment.get("score") if result.risk_assessment else 0,
            "risk_rationale": result.risk_assessment.get("rationale") if result.risk_assessment else "",
            "param_interpretation": result.param_interpretation,
            "synthesis_report": result.synthesis_report,
            "recommendations": result.recommendations,
            "patterns": result.patterns,
            "context_analysis": result.context_analysis,
            "rag_collection_name": result.rag_collection_name,
            "errors": result.errors
        }
        
        return response_data

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
def chat_with_report(request: ChatRequest):
    try:
        if not request.collection_name:
             raise HTTPException(status_code=400, detail="Collection name is required")
             
        answer = rag_retrieve_and_answer(request.question, request.collection_name, request.session_id)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Health AI API is running"}
