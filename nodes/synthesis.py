from utils.llm_utils import get_llm

def synthesis_node(state):
    """
    Aggregates findings from Parameter Extraction, Pattern Recognition, and Contextual Analysis
    into a coherent summary.
    """
    validated = state.validated_params
    patterns = state.patterns
    risk = state.risk_assessment
    context = state.context_analysis
    patient_info = state.patient_info or {}
    
    if not validated:
        return {"synthesis_report": "No data available to synthesize."}

    llm = get_llm()
    
    # Prepare prompt inputs
    prompt = f"""
    You are a senior medical consultant. Synthesize a comprehensive report based on the following:
    
    PATIENT: {patient_info.get('Name', 'Unknown')} | {patient_info.get('Age', 'Unknown')} | {patient_info.get('Gender', 'Unknown')}
    
    1. ABNORMAL FINDINGS (Validated Data):
    {
        ", ".join([f"{k}: {v['value']}" for k,v in validated.items() if state.param_interpretation.get(k, {}).get("status") != "normal"])
    }
    
    2. DETECTED PATTERNS:
    {", ".join(patterns)}
    
    3. RISK ASSESSMENT:
    Score: {risk.get('score')}
    Rationale: {risk.get('rationale')}
    
    4. CONTEXTUAL ANALYSIS:
    {context.get('analysis')}
    
    Write a clear, professional summary for the patient (layperson friendly but medically accurate).
    
    FORMATTING RULES (STRICT):
    1. Be CONCISE. limit the report to the most essential information.
    2. Do NOT use markdown headers (like # or ##). Instead, use **Bold Text** for section titles.
    3. Do NOT use horizontal rules (---) or separators.
    4. Structure the content logically using paragraphs.
    
    IMPORTANT: End the detailed report with this exact signature:
    
    Sincerely,
    
    **J. Likith Sagar**
    Senior Medical Consultant
    """
    
    try:
        response = llm.invoke(prompt)
        return {"synthesis_report": response.content}
    except Exception as e:
        return {"errors": state.errors + [f"Synthesis Node failed: {str(e)}"]}