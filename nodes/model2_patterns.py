import logging
from typing import List
from pydantic import BaseModel, Field
from utils.llm_utils import get_fast_llm, get_llm, get_fallback_llm

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
    
    # Determine report type for panel-specific context
    report_type = getattr(state, "report_type", None) or "UNKNOWN"

    prompt = f"""
        You are an expert medical AI assistant specialized in clinical laboratory interpretation.
        You operate as a STRICT rule-based pattern recognition system.
        Do NOT infer beyond the rules below.

        Report Type: {report_type}

        Patient Info:
        Name: {patient_info.get('Name', 'Unknown')}
        Age: {patient_info.get('Age', 'Unknown')}
        Gender: {patient_info.get('Gender', 'Unknown')}

        Lab Results (may include CBC, LFT, KFT, Lipid, Thyroid, or other panels):
        {data_str}

        ====================
        CRITICAL INTERPRETATION RULES (NON-NEGOTIABLE)
        ====================

        1. TAG PRIORITY RULE
        - If a parameter has an explicit tag (LOW / NORMAL / HIGH / BORDERLINE / UNKNOWN),
          TREAT THE TAG AS GROUND TRUTH.
        - IGNORE numeric intuition if the tag says NORMAL.
        - Parameters with UNKNOWN flag: include only if value strongly suggests abnormality.

        2. FALLBACK RULE (WHEN TAGS ARE ABSENT)
        - Use reference range + units to infer LOW / NORMAL / HIGH if available.
        - If reference range is missing → classify as "UNDETERMINED" — do NOT use for diagnosis.

        3. UNIT AWARENESS RULE (CRITICAL)
        - NEVER mix percentages (%) with absolute counts.
        - Cytopenias: diagnose ONLY using absolute counts or explicit LOW tags.

        ====================
        HAEMATOLOGY PATTERNS (CBC)
        ====================

        Anemia Patterns:
        - Microcytic Anemia:     LOW Hemoglobin + LOW MCV
        - Macrocytic Anemia:     LOW Hemoglobin + HIGH MCV
        - Normocytic Anemia:     LOW Hemoglobin + NORMAL MCV
        - Iron Deficiency Anemia: LOW Hemoglobin + LOW MCV + LOW Ferritin (if present)

        White Cell Patterns:
        - Leukopenia:            LOW Total WBC
        - Leukocytosis:          HIGH Total WBC
        - Neutropenia:           LOW Absolute Neutrophils / ANC
        - Lymphopenia:           LOW Absolute Lymphocytes
        - Acute Infection:       HIGH WBC + HIGH Neutrophils
        - Chronic/Viral Pattern: HIGH Absolute Lymphocytes
        - Pancytopenia:          LOW WBC + LOW Hemoglobin + LOW Platelets

        Platelet Patterns:
        - Thrombocytopenia:      LOW Platelets
        - Thrombocytosis:        HIGH Platelets

        RBC Concentration:
        - Polycythemia:          HIGH Hemoglobin + HIGH PCV
        - Hemoconcentration:     HIGH PCV + Normal/Low Hemoglobin

        ====================
        LIVER FUNCTION PATTERNS (LFT)
        ====================

        - Hepatocellular Injury:   HIGH ALT + HIGH AST (ALT > AST suggests viral/toxic)
        - Cholestatic Pattern:     HIGH ALP + HIGH GGT (with or without elevated bilirubin)
        - Obstructive Jaundice:    HIGH Total Bilirubin + HIGH Direct Bilirubin + HIGH ALP
        - Hepatic Synthetic Defect: LOW Albumin + LOW Total Protein
        - Mixed Liver Disease:     HIGH transaminases + HIGH bilirubin + LOW albumin

        ====================
        KIDNEY FUNCTION PATTERNS (KFT)
        ====================

        - Acute/Chronic Kidney Disease: HIGH Creatinine + HIGH BUN/Urea
        - Hyperuricemia:           HIGH Uric Acid
        - Electrolyte Imbalance:   LOW/HIGH Sodium or Potassium (flag immediately if critical)
        - Hyponatremia:            LOW Sodium (<135 mEq/L)
        - Hyperkalemia:            HIGH Potassium (>5.5 mEq/L — life-threatening)

        ====================
        LIPID PANEL PATTERNS
        ====================

        - Dyslipidemia:            HIGH Total Cholesterol + HIGH LDL + LOW HDL
        - Hypertriglyceridemia:    HIGH Triglycerides (>500 = pancreatitis risk)
        - Low HDL Syndrome:        LOW HDL (cardiovascular risk)
        - Metabolic Syndrome:      HIGH Triglycerides + LOW HDL + HIGH glucose (if present)

        ====================
        THYROID PATTERNS
        ====================

        - Hypothyroidism:          HIGH TSH + LOW Free T4 (or LOW Total T4)
        - Hyperthyroidism:         LOW TSH + HIGH Free T4 (or HIGH T3)
        - Subclinical Hypothyroid: HIGH TSH + NORMAL T4
        - Subclinical Hyperthyroid: LOW TSH + NORMAL T4/T3

        ====================
        DIABETES / GLUCOSE PATTERNS
        ====================

        - Impaired Fasting Glucose: FBS 100–125 mg/dL
        - Diabetes Mellitus:        FBS ≥126 mg/dL or HbA1c ≥6.5%
        - Poor Glycemic Control:    HIGH HbA1c (>8% = poor; >10% = very poor)

        ====================
        RISK SCORING RULES
        ====================

        - 1–3: Single mild abnormality, no dangerous combinations
        - 4–6: One clear syndrome OR multiple mild abnormalities
        - 7–8: Multiple related abnormalities OR one severe syndrome
        - 9–10: Life-threatening patterns (severe anemia, pancytopenia, hyperkalemia,
                critical liver failure, pancreatitis-level triglycerides)

        ====================
        CONFLICT RESOLUTION
        ====================

        - If two detected patterns contradict each other → prioritize the one
          supported by the most primary markers (Hemoglobin for anemia, etc.)
        - SUPPRESS contradicted diagnosis and explain why.

        ====================
        TASK
        ====================

        1. Identify ONLY valid clinical patterns using the rules above.
        2. Assign a Risk Score (1–10).
        3. Provide Risk Rationale (List[str]):
           - Mention ONLY confirmed abnormal values.
           - Explain WHY their combination matters for THIS patient.
           - If no syndrome is detected, clearly state: "No significant abnormal patterns detected."

        OUTPUT FORMAT (JSON ONLY):
        {parser.get_format_instructions()}

    """

    def _invoke_with_fallback(p):
        try:
            return parser.invoke(get_fast_llm().invoke(p))
        except Exception as e:
            logger.warning(f"model2_patterns fast model failed: {e}. Trying quality model.")
            return parser.invoke(get_llm().invoke(p))

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