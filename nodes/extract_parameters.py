import logging
from typing import Optional, Union
from pydantic import BaseModel, Field
from utils.llm_utils import get_llm, get_fallback_llm

logger = logging.getLogger(__name__)

class ExtractedValue(BaseModel):
    value: float = Field(description="The numeric value extracted.")
    unit: Optional[str] = Field(description="The unit of the value found in text.")

class ExtractionOutput(BaseModel):
    # Allow strings because LLMs often quote numbers (e.g. "12.5") failing strict float validation
    Hemoglobin: Optional[Union[float, str]] = None
    RBC: Optional[Union[float, str]] = Field(None, description="Total RBC Count")
    PCV: Optional[Union[float, str]] = Field(None, description="Packed Cell Volume / Hematocrit")
    MCV: Optional[Union[float, str]] = None
    MCH: Optional[Union[float, str]] = None
    MCHC: Optional[Union[float, str]] = None
    RDW: Optional[Union[float, str]] = None
    WBC: Optional[Union[float, str]] = Field(None, description="Total WBC Count")
    Neutrophils: Optional[Union[float, str]] = None
    Lymphocytes: Optional[Union[float, str]] = None
    Eosinophils: Optional[Union[float, str]] = None
    Monocytes: Optional[Union[float, str]] = None
    Basophils: Optional[Union[float, str]] = None
    Platelets: Optional[Union[float, str]] = Field(None, description="Platelet Count")
    ESR: Optional[Union[float, str]] = None
    MPV: Optional[Union[float, str]] = None
    PDW: Optional[Union[float, str]] = None
    PCT: Optional[Union[float, str]] = None
    
    # Patient Demographics
    PatientName: Optional[str] = None
    Age: Optional[Union[str, int]] = None
    Gender: Optional[str] = None


# Expected units for display fallback
DEFAULT_UNITS = {
    "Hemoglobin": "g/dL",
    "Total RBC count": "mill/cumm",
    "Packed Cell Volume": "%",
    "MCV": "fL",
    "MCH": "pg",
    "MCHC": "g/dL",
    "RDW": "%",
    "Total WBC count": "cumm",
    "Neutrophils": "%",
    "Lymphocytes": "%",
    "Eosinophils": "%",
    "Monocytes": "%",
    "Basophils": "%",
    "Platelet Count": "cumm",
    "ESR": "mm/hr",
    "MPV": "fL",
    "PDW": "%",
    "PCT": "%",
    "Absolute Neutrophils": "cumm",
    "Absolute Lymphocytes": "cumm",
    "Absolute Eosinophils": "cumm",
    "Absolute Monocytes": "cumm",
    "Absolute Basophils": "cumm",
}

def _parse_float(val: Union[float, str, None]) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, float) or isinstance(val, int):
        return float(val)
    try:
        # cleanup string "12.5 g/dL" -> 12.5
        clean = str(val).replace(",", "").strip()
        # Extract first number if mixed text
        import re
        match = re.search(r"(\d+(\.\d+)?)", clean)
        if match:
            return float(match.group(1))
        return float(clean)
    except:
        return None

def extract_parameters_node(state):
    """
    Refined extraction using LLM to parse complex tables.
    Matches standard keys to state.extracted_params structure.
    """
    text = state.raw_text or ""
    if not text.strip():
        return {"extracted_params": {}, "errors": state.errors + ["No text to extract from."]}

    from langchain_core.output_parsers import PydanticOutputParser
    parser = PydanticOutputParser(pydantic_object=ExtractionOutput)
    
    prompt = f"""
        You are a medical data extraction engine specialized in CBC (Complete Blood Count) reports.
        Your task is STRICT STRUCTURED EXTRACTION — NOT interpretation, NOT diagnosis.

        The output MUST strictly follow the provided Pydantic schema.

        INPUT:
        Raw OCR text extracted from a blood report.
        The text may contain:
        - OCR errors
        - Misaligned columns
        - Reference ranges
        - Units in different formats
        - Percent and absolute values together
        - Regional number formats (Indian, US, EU)
        {text}

        ====================
        GLOBAL EXTRACTION RULES (MANDATORY)
        ====================

        1. RESULT-ONLY RULE
        - Extract ONLY the actual patient RESULT value for each parameter.
        - DO NOT extract:
        - Reference range values
        - Column headers
        - Unit-only numbers
        - Methodology text
        - If multiple numbers appear in the same row:
        - Choose the number that represents the patient result,
            not the reference range.

        2. UNIT AWARENESS & DISAMBIGUATION (CRITICAL)
        - Identify whether a value represents:
        - Percentage (%)
        - Absolute count (×10³/µL, ×10⁹/L, cells/mm³, /cumm)
        - NEVER treat absolute counts as percentages or vice versa.

        - If both % and absolute values appear:
        - Store percentage in the main field (e.g., Neutrophils)
        - Store absolute count ONLY if a dedicated absolute field exists
        - Otherwise, IGNORE the absolute value

        3. DO NOT INFER OR CORRECT VALUES
        - Do NOT apply medical judgment.
        - Do NOT validate whether a value is normal or abnormal.
        - Do NOT infer LOW/HIGH from numeric intuition.

        4. FLAG HANDLING
        - If the report explicitly shows a flag (LOW, HIGH, NORMAL, BORDERLINE, CRITICAL),
        extract ONLY the RESULT value — NOT the flag.
        - Flags are NOT part of this extraction schema.

        5. PLATELET COUNT SANITY RULE (OCR-SPECIFIC)
        - If Platelet Count appears between 10000–30000 AND:
        - The reference range lower bound is ≥150000
        - AND the row is marked NORMAL or has no LOW/CRITICAL indication
        → Assume OCR missed a zero → multiply by 10
        (e.g., 20000 → 200000)
        - If Platelet Count is flagged LOW or CRITICAL:
        → Trust the extracted value as-is

        6. NUMBER NORMALIZATION
        - Normalize textual numbers:
        - "1.5 lakhs" → 150000
        - "2 lakh" → 200000
        - "4.5 million" → 4.5
        - Normalize separators:
        - "1,50,000" → 150000
        - "4,50,000" → 450000
        - Handle decimal commas ONLY when context clearly indicates decimals:
        - "4,5" → 4.5

        7. MISSING OR AMBIGUOUS DATA
        - If a parameter is listed but the value is missing, unreadable,
        or cannot be confidently identified → return null.
        - Never guess.

        8. PATIENT DEMOGRAPHICS
        - Extract Patient Name, Age, and Gender ONLY if explicitly present.
        - Do NOT infer gender from name.
        - Age may be numeric or text (e.g., "28 Years").

        ====================
        PARAMETERS TO EXTRACT
        ====================

        CBC Parameters:
        - Hemoglobin
        - RBC
        - PCV
        - MCV
        - MCH
        - MCHC
        - RDW
        - WBC
        - Platelets
        - ESR
        - MPV
        - PDW
        - PCT

        Differential (PERCENT ONLY unless absolute field exists):
        - Neutrophils
        - Lymphocytes
        - Eosinophils
        - Monocytes
        - Basophils

        Patient Info:
        - PatientName
        - Age
        - Gender

        ====================
        OUTPUT REQUIREMENTS
        ====================

        - Output MUST be valid JSON.
        - Output MUST strictly match the Pydantic schema.
        - Use null for missing values.
        - Do NOT add explanations, comments, or extra fields.

        ====================
        FINAL OUTPUT FORMAT
        ====================
        {parser.get_format_instructions()}
    """
    
    extracted = {}
    patient_info = {}

    def _invoke_with_fallback(p):
        """Try primary model, fall back to secondary on failure."""
        try:
            llm = get_llm()
            resp = llm.invoke(p)
            return parser.invoke(resp)
        except Exception as e:
            logger.warning(f"extract_parameters primary model failed: {e}. Trying fallback.")
            llm2 = get_fallback_llm()
            resp2 = llm2.invoke(p)
            return parser.invoke(resp2)

    try:
        res = _invoke_with_fallback(prompt)
        logger.info("extract_parameters: LLM extraction succeeded")

        # Map back to internal keys
        mapping = {
            "Hemoglobin": "Hemoglobin",
            "RBC": "Total RBC count",
            "PCV": "Packed Cell Volume",
            "MCV": "MCV",
            "MCH": "MCH",
            "MCHC": "MCHC",
            "RDW": "RDW",
            "WBC": "Total WBC count",
            "Neutrophils": "Neutrophils",
            "Lymphocytes": "Lymphocytes",
            "Eosinophils": "Eosinophils",
            "Monocytes": "Monocytes",
            "Basophils": "Basophils",
            "Platelets": "Platelet Count",
            "ESR": "ESR",
            "MPV": "MPV",
            "PDW": "PDW",
            "PCT": "PCT",
        }
        
        for attr, canonical in mapping.items():
            raw = getattr(res, attr)
            val = _parse_float(raw)
            if val is not None:
                extracted[canonical] = {
                    "raw_value": raw,
                    "value": val,
                    "unit": DEFAULT_UNITS.get(canonical),
                    "scale_note": "Extracted by LLM"
                }

        if res.PatientName: patient_info["Name"] = res.PatientName
        if res.Age: patient_info["Age"] = str(res.Age)
        if res.Gender: patient_info["Gender"] = res.Gender

    except Exception as e:
        logger.error(f"extract_parameters: all models failed: {e}")
        return {"extracted_params": {}, "errors": state.errors + [f"LLM Extraction failed: {str(e)}"]}

    return {"extracted_params": extracted, "patient_info": patient_info}