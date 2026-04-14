import logging
from typing import List
from pydantic import BaseModel, Field
from utils.llm_utils import get_llm, get_fallback_llm

logger = logging.getLogger(__name__)

class PatternOutput(BaseModel):
    patterns: List[str] = Field(description="List of identified clinical patterns (e.g., 'Microcytic Anemia', 'Leukocytosis')")
    risk_score: int = Field(description="Risk score from 1-10 (10 being highest risk)")
    risk_rationale: List[str] = Field(description="List of key reasons for the risk score (concise bullet points)")

def model2_patterns_node(state):
    """
    Analyzes validated parameters to identify patterns and assess risk.
    """
    validated = state.validated_params
    patient_info = state.patient_info or {}
    
    if not validated:
        return {"patterns": [], "risk_assessment": {}}

    from langchain_core.output_parsers import PydanticOutputParser
    parser = PydanticOutputParser(pydantic_object=PatternOutput)

    # Use interpreted data from Model 1 if available
    interpreted = state.param_interpretation or {}
    
    # Format input for LLM with explicit status (LOW/NORMAL/HIGH)
    data_lines = []
    if interpreted:
        for k, v in interpreted.items():
            status = v.get("status", "unknown").upper()
            ref_str = f"[{v['reference'].get('low')}-{v['reference'].get('high')}]" if v.get('reference') else ""
            data_lines.append(f"{k}: {v['value']} {v.get('unit','')} ({status}) {ref_str}")
    else:
        # Fallback to raw validated params if Model 1 failed (unlikely)
        data_lines = [f"{k}: {v['value']} {v.get('unit','')}" for k, v in validated.items()]
            
    data_str = "\n".join(data_lines)
    
    # Prompt Augmentation
    prompt = f"""
        You are an expert medical AI assistant specialized in hematology.
        You operate as a STRICT rule-based pattern recognition system.
        Do NOT infer beyond the rules below.

        Patient Info:
        Name: {patient_info.get('Name', 'Unknown')}
        Age: {patient_info.get('Age', 'Unknown')}
        Gender: {patient_info.get('Gender', 'Unknown')}

        Input:
        CBC blood test results (may include values, units, reference ranges,
        and optional LOW/NORMAL/HIGH/BORDERLINE tags):
        {data_str}

        ====================
        CRITICAL INTERPRETATION RULES (NON-NEGOTIABLE)
        ====================

        1. TAG PRIORITY RULE
        - If a parameter has an explicit tag (LOW / NORMAL / HIGH / BORDERLINE),
        TREAT THE TAG AS GROUND TRUTH.
        - IGNORE numeric intuition if the tag says NORMAL.
        - NEVER override a NORMAL tag using personal medical knowledge.

        2. FALLBACK RULE (WHEN TAGS ARE ABSENT)
        - If NO explicit tag is provided:
        - Use reference range + units to infer LOW / NORMAL / HIGH.
        - If reference range is missing or unclear → classify as "UNDETERMINED"
            and DO NOT use it for syndrome detection.

        3. UNIT AWARENESS RULE (CRITICAL)
        - NEVER mix percentages (%) with absolute counts (×10³/µL, cells/mm³).
        - Percentages describe DISTRIBUTION, not cytopenia.
        - Cytopenias MUST be diagnosed ONLY using:
        - Absolute counts OR explicit LOW tags.
        - If both % and absolute values are present:
        - PRIORITIZE absolute counts.

        4. FOCUS RULE
        - Consider ONLY parameters tagged or inferred as:
        LOW, HIGH, or BORDERLINE.
        - If no such parameters exist:
        - Explicitly state: "No abnormal hematologic patterns detected."

        ====================
        SYNDROME DETECTION RULES (STRICT)
        ====================

        Anemia Patterns:
        - Microcytic Anemia:
        LOW Hemoglobin + LOW MCV
        - Macrocytic Anemia:
        LOW Hemoglobin + HIGH MCV
        - Normocytic Anemia:
        LOW Hemoglobin + NORMAL MCV

        White Cell Patterns:
        - Leukopenia:
        LOW Total WBC
        - Leukocytosis:
        HIGH Total WBC
        - Neutropenia:
        LOW Absolute Neutrophil Count (ANC)
        - Lymphopenia:
        LOW Absolute Lymphocyte Count (ALC)
        - Acute Infection Pattern:
        HIGH WBC + HIGH Neutrophils
        - Chronic / Viral Pattern:
        HIGH Absolute Lymphocytes

        Platelet Patterns:
        - Thrombocytopenia:
        LOW Platelets
        - Borderline Thrombocytopenia:
        BORDERLINE Platelets
        (do NOT escalate unless other cytopenias exist)

        Red Cell Concentration Patterns:
        - Polycythemia:
        HIGH Hemoglobin + HIGH PCV
        - Hemoconcentration / Dehydration (Relative):
        HIGH PCV + Hemoglobin LOW or NORMAL
        (DO NOT label polycythemia)

        ====================
        CONFLICT RESOLUTION (MANDATORY)
        ====================

        - If two detected patterns are physiologically contradictory
        (e.g., Anemia and Polycythemia):
        - PRIORITIZE diagnoses supported by Hemoglobin.
        - SUPPRESS the conflicting diagnosis.
        - Explicitly explain why it was suppressed.

        ====================
        RISK SCORING RULES
        ====================

        - 1–3:
        Single mild abnormality, no dangerous combinations
        - 4–6:
        One clear syndrome OR multiple mild abnormalities
        - 7–8:
        Multiple related cytopenias OR one severe syndrome
        - 9–10:
        Life-threatening patterns
        (e.g., severe anemia, pancytopenia, sepsis pattern)

        ====================
        TASK
        ====================

        1. Identify ONLY valid clinical patterns using the rules above.
        2. Assign a Risk Score (1–10).
        3. Provide Risk Rationale (List[str]):
        - Mention ONLY confirmed abnormal values.
        - Explain WHY their combination matters for THIS patient.
        - Do NOT include textbook explanations.
        - If no syndrome is detected, clearly state this.

        ====================
        OUTPUT FORMAT (JSON ONLY)
        ====================
        {parser.get_format_instructions()}

    """

    def _invoke_with_fallback(p):
        try:
            return parser.invoke(get_llm().invoke(p))
        except Exception as e:
            logger.warning(f"model2_patterns primary failed: {e}. Trying fallback.")
            return parser.invoke(get_fallback_llm().invoke(p))

    try:
        parsed_response = _invoke_with_fallback(prompt)
        # Clamp risk score to valid range
        score = max(1, min(10, parsed_response.risk_score))
        logger.info(f"model2_patterns: {len(parsed_response.patterns)} patterns, risk={score}")
        return {
            "patterns": parsed_response.patterns,
            "risk_assessment": {
                "score": score,
                "rationale": parsed_response.risk_rationale,
            },
        }
    except Exception as e:
        logger.error(f"model2_patterns all models failed: {e}")
        return {"errors": state.errors + [f"Model 2 (Patterns) failed: {str(e)}"]}