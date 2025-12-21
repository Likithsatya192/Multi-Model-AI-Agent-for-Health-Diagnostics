import streamlit as st
import tempfile
import pandas as pd
import matplotlib.pyplot as plt
from io import StringIO

from graph.run_pipeline import run_full_pipeline

# Streamlit Config
st.set_page_config(
    page_title="CBC Analyzer",
    page_icon="🩸",
    layout="wide"
)

st.title("🩸 Instant CBC Analysis")
st.caption("Upload Patient Lab Report (PDF/Image)")

uploaded = st.file_uploader(
    "Upload Report",
    type=["pdf", "jpg", "jpeg", "png"],
    help="Supports PDF or common image formats."
)

if uploaded:
    # Save temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded.name.split('.')[-1]}") as tmp:
        tmp.write(uploaded.read())
        file_path = tmp.name

    with st.status("Processing report… please wait", expanded=False) as status:
        result = run_full_pipeline(file_path)
        status.update(label="Processing complete", state="complete")

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
    if result.param_interpretation:
        # Sort keys to keep similar items together or just alpha
        params = sorted(result.param_interpretation.items())
        
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
        if result.patterns:
            for pat in result.patterns:
                st.write(f"- 🔍 **{pat}**")
        else:
            st.info("No specific patterns detected.")
            
        if result.risk_assessment:
            score = result.risk_assessment.get("score", 0)
            color = "green" if score < 4 else "orange" if score < 7 else "red"
            st.markdown(f"**Risk Score:** :{color}[{score}/10]")
            rationale = result.risk_assessment.get('rationale', [])
            st.markdown("**Rationale:**")
            if isinstance(rationale, list):
                for item in rationale:
                    st.write(f"- {item}")
            else:
                st.write(rationale)

    with col2:
        st.subheader("Contextual Analysis")
        ctx = result.context_analysis
        if ctx:
            st.markdown(f"**Analysis:** {ctx.get('analysis', 'N/A')}")
            if ctx.get("adjusted_concerns"):
                st.markdown(f"**Notes:** {ctx.get('adjusted_concerns')}")
        else:
            st.info("No contextual analysis available.")

    st.divider()
    
    st.subheader("📑 Synthesis Report")
    if result.synthesis_report:
        st.markdown(result.synthesis_report)
    else:
        st.info("Report generation pending.")

    st.subheader("💡 Personalized Recommendations")
    if result.recommendations:
        for rec in result.recommendations:
            st.info(f"👉 {rec}")
    else:
        st.write("No specific recommendations.")

    # ==========================
    # 6) Errors & Warnings
    # ==========================
    if result.errors:
        st.subheader("⚠️ Warnings / Errors")
        for err in result.errors:
            st.error(err)