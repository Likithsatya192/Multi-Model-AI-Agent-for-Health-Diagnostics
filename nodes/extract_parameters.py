from typing import Optional, Union
from pydantic import BaseModel, Field
from utils.llm_utils import get_llm

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

    llm = get_llm()
    # structured_llm = llm.with_structured_output(ExtractionOutput)
    from langchain_core.output_parsers import PydanticOutputParser
    parser = PydanticOutputParser(pydantic_object=ExtractionOutput)
    
    prompt = f"""
    Extract CBC blood test parameters and patient info from the following OCR text.
    
    TEXT:
    {text}
    
    RULES:
    1. Extract ONLY the "Result" value. Do not extract Reference Range numbers!
    2. Platelet Count Sanity Check:
       - If the text says "20000" but the reference range is 150000+, reports sometimes omit the last zero or OCR misses it.
       - IF the row says "Normal" but the value is 20,000, it is likely 200,000. Extract 200000.
       - IF the row says "Low" or has no flag, trust the 20,000.
    3. Formatting:
       - "1.5 lakhs" -> 150000.
       - "4.5 million" -> 4.5.
    4. If a value is missing, return null.
    
    {parser.get_format_instructions()}
    """
    
    extracted = {}
    patient_info = {}
    
    try:
        response = llm.invoke(prompt)
        res = parser.invoke(response)
        
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
        # Fallback? Or just report error.
        return {"extracted_params": {}, "errors": state.errors + [f"LLM Extraction failed: {str(e)}"]}

    return {"extracted_params": extracted, "patient_info": patient_info}