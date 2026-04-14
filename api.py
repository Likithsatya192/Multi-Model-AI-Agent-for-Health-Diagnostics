import asyncio
import os
import shutil
import logging
import tempfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from graph.run_pipeline import run_full_pipeline
from nodes.rag_node import rag_retrieve_and_answer, store_report_state

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}',
)
logger = logging.getLogger("api")

# ── Startup validation ────────────────────────────────────────────────────────
_REQUIRED_ENV = ["GROQ_API_KEY"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(f"Missing required env vars at startup: {missing}")
    logger.info('"Server startup OK — all required env vars present"')
    yield
    logger.info('"Server shutting down"')

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Health AI API",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
_ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}


# ── Schemas ───────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    collection_name: str = Field(..., min_length=10, max_length=80)
    session_id: str = Field(None, max_length=64)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _validate_upload(file: UploadFile, size: int):
    if size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max allowed: {MAX_FILE_SIZE_BYTES // (1024*1024)} MB.",
        )
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )
    return ext


# ── Routes ────────────────────────────────────────────────────────────────────
@app.post("/analyze")
@limiter.limit("10/minute")
async def analyze_report(
    request: Request,
    file: UploadFile = File(...),
    session_id: str = Form(None),
):
    logger.info(f'"analyze request" "file":"{file.filename}" "session":"{session_id}"')

    # Read file into memory first to check size
    contents = await file.read()
    ext = _validate_upload(file, len(contents))

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(run_full_pipeline, tmp_path),
                timeout=300.0,  # 5-minute hard limit
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail="Analysis timed out. Large or complex reports may take longer — please try again.",
            )

        if session_id:
            store_report_state(session_id, result)

        response_data = {
            "report_type": result.report_type or "UNKNOWN",
            "risk_score": result.risk_assessment.get("score") if result.risk_assessment else 0,
            "risk_rationale": result.risk_assessment.get("rationale") if result.risk_assessment else "",
            "param_interpretation": result.param_interpretation,
            "synthesis_report": result.synthesis_report,
            "recommendations": result.recommendations,
            "patterns": result.patterns,
            "context_analysis": result.context_analysis,
            "rag_collection_name": result.rag_collection_name,
            "errors": result.errors,
        }
        logger.info(f'"analyze complete" "session":"{session_id}" "patterns":{len(result.patterns)} "errors":{len(result.errors)}')
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f'"analyze failed" "error":"{e}"')
        raise HTTPException(status_code=500, detail="Analysis failed. Please try again.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError as oe:
                logger.warning(f'"temp file cleanup failed" "path":"{tmp_path}" "err":"{oe}"')


@app.post("/chat")
@limiter.limit("30/minute")
def chat_with_report(request: Request, body: ChatRequest):
    logger.info(f'"chat request" "collection":"{body.collection_name}" "session":"{body.session_id}"')
    try:
        answer = rag_retrieve_and_answer(
            body.question, body.collection_name, body.session_id
        )
        return {"answer": answer}
    except Exception as e:
        logger.exception(f'"chat failed" "error":"{e}"')
        raise HTTPException(status_code=500, detail="Chat failed. Please try again.")


@app.get("/health")
def health_check():
    """Real health check — verifies env vars and Groq key presence."""
    checks = {}
    checks["groq_key_set"] = bool(os.environ.get("GROQ_API_KEY"))
    checks["faiss_dir_writable"] = os.access(
        os.environ.get("FAISS_INDEX_DIR", "faiss_index"), os.W_OK
    ) if os.path.exists(os.environ.get("FAISS_INDEX_DIR", "faiss_index")) else True

    all_ok = all(checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
    )
