import streamlit as st
import tempfile
import pandas as pd
import matplotlib.pyplot as plt
import uuid
import fitz  # PyMuPDF
from PIL import Image
from io import StringIO
import requests
import os

# Backend URL — set BACKEND_URL env var or default to localhost
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")

# For local dev: fall back to direct pipeline calls if backend unreachable
try:
    from graph.run_pipeline import run_full_pipeline
    from graph.rag_pipeline import run_rag_pipeline
    LOCAL_FALLBACK = True
except ImportError:
    LOCAL_FALLBACK = False


# Backend API Helpers
def call_backend_analyze(file_bytes, filename, session_id=None):
    """Call backend /analyze endpoint. Falls back to local if unavailable."""
    try:
        files = {"file": (filename, file_bytes)}
        data = {"session_id": session_id} if session_id else {}
        response = requests.post(f"{BACKEND_URL}/analyze", files=files, data=data, timeout=300)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        if LOCAL_FALLBACK:
            st.warning(f"Backend unavailable, using local pipeline. Error: {e}")
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{filename.split('.')[-1]}") as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            result = run_full_pipeline(tmp_path)
            import os
            os.remove(tmp_path)
            # Convert to dict for consistency
            return {
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
        else:
            st.error(f"Backend error: {e}")
            raise


def call_backend_chat(question, collection_name, session_id=None):
    """Call backend /chat endpoint. Falls back to local if unavailable."""
    try:
        payload = {
            "question": question,
            "collection_name": collection_name,
            "session_id": session_id,
        }
        response = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()["answer"]
    except requests.RequestException as e:
        if LOCAL_FALLBACK:
            st.warning(f"Backend unavailable, using local RAG. Error: {e}")
            return run_rag_pipeline(question, collection_name, session_id)
        else:
            st.error(f"Backend error: {e}")
            raise

# Streamlit Config
st.set_page_config(
    page_title="CBC Analyzer",
    page_icon="🩸",
    layout="wide"
)

# Centered Title
st.markdown("<h1 style='text-align: center; font-weight: bold;'>🩸 Instant CBC Analysis</h1>", unsafe_allow_html=True)

with st.sidebar:
    st.caption("Upload Patient Lab Report (PDF/Image)")

    uploaded = st.file_uploader(
        "Upload Report",
        type=["pdf", "jpg", "jpeg", "png"],
        help="Supports PDF or common image formats."
    )
    
    if uploaded:
        st.divider()
        st.markdown("**📄 File Preview**")
        try:
            # Check file type
            if uploaded.type == "application/pdf":
                # Create a temporary file to read with fitz if simple bytes usage fails or just use bytes
                # fitz.open(stream=..., filetype="pdf") works with bytes
                doc = fitz.open(stream=uploaded.read(), filetype="pdf")
                uploaded.seek(0) # Reset pointer for later use
                
                if len(doc) > 0:
                    page = doc.load_page(0)  # number of page
                    pix = page.get_pixmap()
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    st.image(img, caption="Page 1 Preview", width='stretch')
            else:
                st.image(uploaded, caption="Uploaded Image", width='stretch')
        except Exception as e:
            st.error(f"Could not detail preview: {e}")

# Main Logic
if uploaded:
    # Check if we need to re-run analysis
    # Condition: No result in session OR new file uploaded (name changed)
    if "analysis_result" not in st.session_state or st.session_state.get("last_uploaded_file") != uploaded.name:
        with st.status("Processing report… please wait", expanded=False) as status:
            file_bytes = uploaded.read()
            uploaded.seek(0)
            session_id = st.session_state.get("session_id") or str(uuid.uuid4())
            result_dict = call_backend_analyze(file_bytes, uploaded.name, session_id)
            # Store dict directly — already compatible with all downstream access
            st.session_state.analysis_result = result_dict
            st.session_state.session_id = session_id
            st.session_state.last_uploaded_file = uploaded.name
            st.session_state.messages = [] # Clear chat history for new report
            status.update(label="Processing complete", state="complete")

    # Retrieve result from session state
    result = st.session_state.analysis_result


    # ==========================
    # Custom CSS for Premium UI
    # ==========================
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }
    
    .main {
        background-color: #0e1117;
    }
    
    h1, h2, h3 {
        color: #e0e0e0; 
        font-weight: 600;
    }
    
    .stAlert {
        border-radius: 8px;
    }
    
    /* Card-like styling for columns */
    div[data-testid="stColumn"] {
        background-color: #1f2937;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #374151;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    hr {
        border-color: #374151;
    }
    </style>
    """, unsafe_allow_html=True)

    # ==========================
    # 3) Model Interpretation
    # ==========================
    st.header("🧠 Multi-Model AI Analysis")

    st.subheader("🧭 Parameter Analysis")
    if result.get("param_interpretation"):
        # Sort keys to keep similar items together or just alpha
        params = sorted(result.get("param_interpretation", {}).items())
        
        # CSS for the custom cards
        st.markdown("""
        <style>
        .metric-card {
            background-color: #1f2937;
            border: 1px solid #374151;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 10px;
        }
        .metric-title {
            color: #9ca3af;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        .metric-value {
            color: #f3f4f6;
            font-size: 1.4em;
            font-weight: 600;
        }
        .metric-unit {
            color: #6b7280;
            font-size: 0.8em;
            margin-left: 5px;
        }
        .status-badge {
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: bold;
            float: right;
        }
        .status-normal { background-color: #064e3b; color: #34d399; }
        .status-high { background-color: #450a0a; color: #f87171; }
        .status-low { background-color: #451a03; color: #fbbf24; }
        .status-header { display: flex; justify-content: space-between; align-items: center; }
        </style>
        """, unsafe_allow_html=True)

        cols = st.columns(3)
        for i, (param, info) in enumerate(params):
            val = info["value"]
            unit = info.get("unit", "")
            ref = info.get("reference", {})
            status = info.get("status", "unknown").lower()
            
            # Badge Color
            status_class = "status-normal"
            if status == "high": status_class = "status-high"
            elif status == "low": status_class = "status-low"
            
            # Simple Progress Bar Logic
            # Normalize value within a broader range [low - margin, high + margin]
            low = ref.get("low", 0)
            high = ref.get("high", 100)
            if low and high:
                span = high - low
                # Determine % position. Cap at 0 and 100.
                # Let's map low->25% and high->75% so we see out-of-bounds
                # 0% = low - 50% span
                # 100% = high + 50% span
                min_disp = low - (span * 0.5)
                max_disp = high + (span * 0.5)
                if max_disp == min_disp: pct = 50
                else: pct = (val - min_disp) / (max_disp - min_disp) * 100
                pct = max(0, min(100, pct))
            else:
                pct = 50 # Default middle if no range
            
            with cols[i % 3]:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="status-header">
                        <span class="metric-title">{param}</span>
                        <span class="status-badge {status_class}">{status.upper()}</span>
                    </div>
                    <div>
                        <span class="metric-value">{val}</span>
                        <span class="metric-unit">{unit}</span>
                    </div>
                    <div style="margin-top: 8px; background-color: #374151; height: 6px; border-radius: 3px; position: relative;">
                         <div style="background-color: #9cb3d9; height: 100%; width: {pct}%; border-radius: 3px; transition: width 0.5s;"></div>
                         <!-- Markers for Low/High could go here but keeping it simple for now -->
                    </div>
                    <div style="font-size: 0.7em; color: #6b7280; margin-top: 4px; display: flex; justify-content: space-between;">
                        <span>{low}</span>
                        <span>Reference</span>
                        <span>{high}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    else:
        st.info("No interpreted results available yet.")

    # ==========================
    # 5) AI Analysis (New)
    # ==========================
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Pattern Recognition")
        if result.get("patterns"):
            for pat in result.get("patterns", []):
                st.write(f"- 🔍 **{pat}**")
        else:
            st.info("No specific patterns detected.")
            
        if result.get("risk_assessment"):
            score = result.get("risk_assessment", {}).get("score", 0)
            color = "green" if score < 4 else "orange" if score < 7 else "red"
            st.markdown(f"**Risk Score:** :{color}[{score}/10]")
            rationale = result.get("risk_assessment", {}).get('rationale', [])
            st.markdown("**Rationale:**")
            if isinstance(rationale, list):
                for item in rationale:
                    st.write(f"- {item}")
            else:
                st.write(rationale)

    with col2:
        st.subheader("Contextual Analysis")
        ctx = result.get("context_analysis")
        if ctx:
            st.markdown(f"**Analysis:** {ctx.get('analysis', 'N/A')}")
            if ctx.get("adjusted_concerns"):
                st.markdown(f"**Notes:** {ctx.get('adjusted_concerns')}")
        else:
            st.info("No contextual analysis available.")

    st.divider()
    
    st.subheader("📑 Synthesis Report")
    if result.get("synthesis_report"):
        st.markdown(result.get("synthesis_report", ""))
    else:
        st.info("Report generation pending.")

    st.subheader("💡 Personalized Recommendations")
    if result.get("recommendations"):
        for rec in result.get("recommendations", []):
            st.info(f"👉 {rec}")
    else:
        st.write("No specific recommendations.")

    # ==========================
    # 6) Errors & Warnings
    # ==========================
    if result.get("errors"):
        st.subheader("⚠️ Warnings / Errors")
        for err in result.get("errors", []):
            st.error(err)

    # ==========================
    # 7) AI Chat Assistant
    # ==========================
    if result.get("rag_collection_name"):
        st.divider()
        st.subheader("💬 Ask AI Assistant")
        
        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []

        if "session_id" not in st.session_state:
            st.session_state.session_id = str(uuid.uuid4())

        # Display chat messages from history on app rerun
        # Sync with backend history for this session if needed, or rely on local state
        # For simplicity, we trust the local state history which mirrors the backend
        
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # React to user input
        if prompt := st.chat_input("Ask a question about this report..."):
            # Display user message in chat message container
            st.chat_message("user").markdown(prompt)
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Get response
            with st.spinner("Thinking..."):
                try:
                    answer = call_backend_chat(
                        prompt,
                        result.get("rag_collection_name"),
                        st.session_state.session_id
                    )
                    # Display assistant response in chat message container
                    with st.chat_message("assistant"):
                        st.markdown(answer)
                    # Add assistant response to chat history
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                except Exception as e:
                    st.error(f"Error generating answer: {e}")