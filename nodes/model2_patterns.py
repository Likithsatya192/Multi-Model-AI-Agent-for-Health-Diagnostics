from typing import List
from pydantic import BaseModel, Field
from utils.llm_utils import get_llm

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

    llm = get_llm()
    # structured_llm = llm.with_structured_output(PatternOutput) # Fails on some models
    
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

        Patient Info:
        Name: {patient_info.get('Name', 'Unknown')}
        Age: {patient_info.get('Age', 'Unknown')}
        Gender: {patient_info.get('Gender', 'Unknown')}

        Analyze the following CBC blood test results:
        {data_str}

        CRITICAL RULES:
        1. RELY on the provided (LOW / NORMAL / HIGH / BORDERLINE) tags.
        These tags are ground truth based on patient-specific reference ranges.
        IGNORE numerical deviations if the tag says NORMAL.

        2. FOCUS ONLY on values tagged as LOW, HIGH, or BORDERLINE.

        3. DETECT SYNDROMES (Pattern Recognition):
        - Microcytic Anemia:
            LOW Hemoglobin + LOW MCV
        - Macrocytic Anemia:
            LOW Hemoglobin + HIGH MCV
        - Normocytic Anemia:
            LOW Hemoglobin + NORMAL MCV
        - Acute Infection:
            HIGH WBC + HIGH Neutrophils (if available)
        - Chronic / Viral Infection:
            HIGH Lymphocytes
        - Thrombocytopenia:
            LOW Platelets
        - Borderline Thrombocytopenia:
            BORDERLINE Platelets (do NOT escalate unless other cytopenias exist)

        4. CUSTOM CHECKS:
        - Consider Polycythemia ONLY if:
            • Hemoglobin is HIGH
            • AND PCV is HIGH
        - If PCV is HIGH but Hemoglobin is LOW or NORMAL:
            • Classify as "Hemoconcentration / Dehydration (Relative)"
            • DO NOT label Polycythemia

        5. CONFLICT RESOLUTION (MANDATORY):
        - If two detected patterns are physiologically contradictory
            (e.g., Anemia and Polycythemia):
            • PRIORITIZE diagnoses supported by Hemoglobin
            • SUPPRESS the conflicting diagnosis
            • Explain the reason clearly

        6. RISK SCORE GUIDELINES:
        - 1–3: Single mild abnormality, no dangerous combinations
        - 4–6: One clear syndrome, mild to moderate severity
        - 7–8: Multiple related abnormalities or one severe syndrome
        - 9–10: Life-threatening patterns
                (e.g., severe anemia, sepsis pattern, pancytopenia)

        TASK:
        1. Identify specific clinical patterns strictly using the rules above.
        2. Assign a Risk Score (1–10) using the Risk Score Guidelines.
        3. Provide Risk Rationale (List[str]):
        - Do NOT give generic textbook definitions.
        - Explain WHY this specific combination is risky or notable
            for THIS patient.
        - Mention the exact abnormal values and their interaction.
        - If a diagnosis is suppressed due to conflict resolution,
            explicitly state why.

        Return the output in the specified JSON format.
        {parser.get_format_instructions()}
    """

    try:
        response = llm.invoke(prompt)
        parsed_response = parser.invoke(response)
        return {
            "patterns": parsed_response.patterns,
            "risk_assessment": {
                "score": parsed_response.risk_score,
                "rationale": parsed_response.risk_rationale
            }
        }
    except Exception as e:
        return {"errors": state.errors + [f"Model 2 (Patterns) failed: {str(e)}"]}