from pydantic import BaseModel
from typing import Dict, Any, Optional, List

class ReportState(BaseModel):
    raw_file_path: Optional[str] = None
    raw_text: Optional[str] = None
    report_type: Optional[str] = None          # detected panel type: CBC, LFT, LIPID, etc.
    extracted_params: Dict[str, Dict[str, Any]] = {}
    validated_params: Dict[str, Dict[str, Any]] = {}
    param_interpretation: Dict[str, Dict[str, Any]] = {}

    # Patient Context
    patient_info: Dict[str, str] = {}
     
    # Model 2 Output
    patterns: List[str] = []
    risk_assessment: Dict[str, Any] = {}
    
    # Model 3 Output
    context_analysis: Dict[str, Any] = {}
    
    # Synthesis & Recommendations
    synthesis_report: Optional[str] = None
    recommendations: List[str] = []
    
    # RAG Context
    rag_collection_name: Optional[str] = None
    
    errors: List[str] = []