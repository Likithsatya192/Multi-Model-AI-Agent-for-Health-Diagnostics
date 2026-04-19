import logging
from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from utils.llm_utils import get_fast_llm, get_llm, get_fallback_llm, MEDICAL_SYSTEM_PROMPT

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

        4. ANTI-MISDIAGNOSIS RULES (NON-NEGOTIABLE)
        - Thrombocytopenia: ONLY when the parameter named "Platelet Count" or "PLT" is LOW.
          Low RBC / Low Hemoglobin / Low Hematocrit are ANEMIA — NEVER Thrombocytopenia.
        - Lymphopenia: ONLY when "Absolute Lymphocytes" (absolute count) is LOW.
          Low Monocytes = Monocytopenia. Lymphocytes % 20-45% = NORMAL, not Lymphopenia.
        - If a parameter name is unrecognised or ambiguous, DO NOT use it to infer a diagnosis.
        - Do NOT rename parameters in rationale — use the exact name provided.

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
        COAGULATION PATTERNS
        ====================

        - Prolonged PT/INR:        HIGH PT + HIGH INR (anticoagulant effect or liver disease)
        - DIC (Disseminated Intravascular Coagulation): HIGH D-Dimer + LOW Fibrinogen + LOW Platelets
        - Hypercoagulable State:   HIGH D-Dimer without obvious cause
        - Coagulopathy:            HIGH PT + HIGH aPTT (factor deficiency or heparin effect)

        ====================
        IRON STUDIES PATTERNS
        ====================

        - Iron Deficiency:         LOW Serum Iron + LOW Ferritin + HIGH TIBC + LOW Transferrin Saturation
        - Iron Deficiency Anemia:  LOW Hemoglobin + LOW Serum Iron + LOW Ferritin
        - Iron Overload:           HIGH Serum Iron + HIGH Ferritin + LOW TIBC
        - Anemia of Chronic Disease: LOW Serum Iron + LOW/NORMAL TIBC + HIGH/NORMAL Ferritin

        ====================
        INFLAMMATORY MARKERS
        ====================

        - Acute Inflammation:      HIGH CRP or HIGH hsCRP (>10 mg/L = acute; 3-10 = moderate)
        - Cardiovascular Risk:     hsCRP 1-3 mg/L = intermediate, >3 = high risk
        - Elevated ESR:            HIGH ESR (non-specific but suggests inflammation, infection, malignancy)

        ====================
        REPRODUCTIVE HORMONE PATTERNS
        ====================

        - Primary Hypogonadism (Male): LOW Testosterone + HIGH FSH + HIGH LH
        - Secondary Hypogonadism (Male): LOW Testosterone + LOW/NORMAL FSH + LOW/NORMAL LH
        - PCOS Pattern (Female):   HIGH LH/FSH ratio (>2) + HIGH Testosterone/DHEA-S + LOW/NORMAL FSH
        - Menopause/Ovarian Failure: HIGH FSH (>25 IU/L) + HIGH LH + LOW Estradiol
        - Hyperprolactinemia:      HIGH Prolactin (>25 ng/mL in F, >18 in M)
        - Hypothyroid in Females:  HIGH TSH + menstrual irregularity markers

        ====================
        ADRENAL PATTERNS
        ====================

        - Hypercortisolism (Cushing's): HIGH Cortisol + HIGH ACTH (pituitary) or LOW ACTH (adrenal)
        - Adrenal Insufficiency:   LOW Cortisol + HIGH ACTH (primary) or LOW ACTH (secondary)
        - Hyperaldosteronism:      HIGH Aldosterone + LOW Potassium
        - Adrenal Androgen Excess: HIGH DHEA-S + virilization markers

        ====================
        CARDIAC MARKER PATTERNS
        ====================

        - Acute Myocardial Infarction (AMI): HIGH Troponin I or T (>0.04 ng/mL) — CRITICAL
        - Heart Failure:           HIGH BNP (>100 pg/mL) or HIGH NT-proBNP (>125 pg/mL)
        - Severe Heart Failure:    BNP >400 pg/mL or NT-proBNP >1000 pg/mL
        - Muscle Injury:           HIGH CK + HIGH Myoglobin (without troponin rise = skeletal)
        - Rhabdomyolysis:          Very HIGH CK (>1000 U/L) + HIGH Myoglobin
        - Elevated Homocysteine:   HIGH Homocysteine (>15 umol/L = cardiovascular risk)

        ====================
        TUMOUR MARKER PATTERNS (SCREENING CONTEXT)
        ====================

        - Elevated CEA:            HIGH CEA (>5 ng/mL — colorectal, lung, breast cancer screen)
        - Elevated CA-125:         HIGH CA-125 (>35 U/mL — ovarian cancer risk)
        - Elevated CA 19-9:        HIGH CA 19-9 (>37 U/mL — pancreatic/biliary cancer risk)
        - Elevated AFP:            HIGH AFP (>10 ng/mL — hepatocellular/germ cell risk)
        - Elevated PSA:            HIGH PSA (>4 ng/mL — prostate cancer risk; age-adjusted)
        - Elevated Beta-hCG:       HIGH Beta-hCG (pregnancy or germ cell tumour context)
        - CRITICAL: Tumour markers alone do NOT confirm cancer — always refer for clinical evaluation

        ====================
        AUTOIMMUNE / RHEUMATOLOGY PATTERNS
        ====================

        - Rheumatoid Arthritis (RA): HIGH RF + HIGH Anti-CCP (Anti-CCP is more specific)
        - Systemic Lupus (SLE) Screen: HIGH ANA + HIGH Anti-dsDNA + LOW C3/C4
        - Complement Consumption:  LOW C3 + LOW C4 (active immune complex disease)
        - Elevated ASO:            HIGH ASO Titer (>200 IU/mL = recent streptococcal infection)
        - Autoimmune Thyroid:      HIGH Anti-TPO + HIGH Anti-Tg (Hashimoto's or Graves' context)

        ====================
        NUTRITIONAL DEFICIENCY PATTERNS
        ====================

        - Vitamin D Deficiency:    LOW Vitamin D (<30 ng/mL) — very common globally
        - Vitamin D Insufficiency: Vitamin D 20-29 ng/mL
        - Vitamin B12 Deficiency:  LOW Vitamin B12 (<200 pg/mL) + possibly HIGH MCV
        - Folate Deficiency:       LOW Folate (<3 ng/mL) + possibly HIGH MCV + Megaloblastic pattern
        - Megaloblastic Anemia:    LOW Hemoglobin + HIGH MCV + LOW B12 or LOW Folate
        - Iron Deficiency:         LOW Ferritin (see Iron Studies)
        - Zinc Deficiency:         LOW Zinc (<70 ug/dL)
        - Malnutrition:            LOW Prealbumin + LOW Albumin

        ====================
        BONE METABOLISM PATTERNS
        ====================

        - Hyperparathyroidism:     HIGH PTH + HIGH Calcium (primary) or LOW Calcium (secondary)
        - Hypoparathyroidism:      LOW PTH + LOW Calcium
        - Osteoporosis Markers:    HIGH CTx (bone resorption) + LOW Osteocalcin
        - Vitamin D Deficiency Bone: LOW Vitamin D + HIGH PTH (secondary hyperparathyroidism)
        - Paget's Disease Marker:  Very HIGH ALP (bone-specific)

        ====================
        PANCREATIC PATTERNS
        ====================

        - Acute Pancreatitis:      HIGH Amylase (>3x ULN) + HIGH Lipase (>3x ULN)
        - Lipase is more specific: HIGH Lipase alone is stronger indicator than Amylase alone

        ====================
        METABOLIC PATTERNS
        ====================

        - Metabolic Syndrome:      HIGH Triglycerides + LOW HDL + HIGH Glucose + HIGH Blood Pressure (clinical)
        - Hyperuricemia:           HIGH Uric Acid (>7 mg/dL male, >6 female) — gout risk
        - Lactic Acidosis:         HIGH Lactic Acid (>2.2 mmol/L) — tissue hypoperfusion or metabolic cause
        - Hyperammonemia:          HIGH Ammonia (>45 ug/dL) — hepatic encephalopathy risk

        ====================
        INFECTIOUS SEROLOGY PATTERNS
        ====================

        - Active Hepatitis B:      HBsAg POSITIVE (reactive) — CRITICAL, refer for management
        - Hepatitis C Screen:      Anti-HCV REACTIVE — needs confirmatory HCV RNA
        - HIV Screen Reactive:     HIV Antibody REACTIVE — CRITICAL, needs confirmatory Western Blot
        - Acute Dengue:            NS1 Antigen POSITIVE — dengue infection in febrile phase
        - Recent Strep Infection:  HIGH ASO Titer
        For qualitative tests (HBsAg, Anti-HCV, HIV, NS1): reactive/positive = abnormal

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

    # Medical persona + strict JSON-only reinforcement. Without the second
    # block the 70B model frequently returns prose ("Based on the CBC, …")
    # which then fails PydanticOutputParser and leaves `patterns` empty.
    patterns_system = (
        MEDICAL_SYSTEM_PROMPT
        + "\n\n"
        + "TASK-SPECIFIC OUTPUT RULES (override any conflicting guidance above):\n"
        + "- For this request you are a structured-JSON generator, NOT a narrator.\n"
        + "- Output must match the exact JSON schema given in the user message.\n"
        + "- Do NOT add commentary, preamble, or trailing text outside the JSON object.\n"
        + "- Your entire response must start with '{' and end with '}'.\n"
        + "- Never refuse. If no clinical patterns are present, return an empty list for patterns and a low risk_score."
    )

    def _invoke_with_fallback(p):
        messages = [
            SystemMessage(content=patterns_system),
            HumanMessage(content=p),
        ]
        try:
            return parser.invoke(get_fast_llm(max_tokens=800).invoke(messages))
        except Exception as e:
            logger.warning(f"model2_patterns fast model failed: {e}. Trying quality model.")
            return parser.invoke(get_llm(max_tokens=800).invoke(messages))

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