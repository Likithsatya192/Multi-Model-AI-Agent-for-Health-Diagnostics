import logging
from typing import List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from utils.llm_utils import get_llm, get_fallback_llm, MEDICAL_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class Recommendation(BaseModel):
    priority: str = Field(
        description="Priority level: 'critical' | 'urgent' | 'follow-up' | 'lifestyle'"
    )
    action: str = Field(
        description="Specific, actionable recommendation in 1-2 sentences."
    )
    reason: str = Field(
        description="Brief clinical reason this recommendation applies to THIS patient's results."
    )


class RecsOutput(BaseModel):
    recommendations: List[Recommendation] = Field(
        description="Ordered list of 4-7 recommendations, most critical first."
    )


def recommendations_node(state):
    """
    Node: Generate prioritised, patient-specific recommendations.

    Uses patterns, risk score, critical flags, and urgency — not just synthesis text.
    Produces structured recommendations with priority levels.
    """
    synthesis = state.synthesis_report or ""
    patterns = state.patterns or []
    risk = state.risk_assessment or {}
    context = state.context_analysis or {}
    interpreted = state.param_interpretation or {}
    patient_info = state.patient_info or {}

    errors = list(getattr(state, "errors", []) or [])

    if not synthesis and not interpreted:
        logger.warning("recommendations: no synthesis or interpretation data")
        return {"recommendations": []}

    # Collect critical and severe params for the prompt
    critical_params = [
        f"{name} = {info['value']} {info.get('unit','')} [{info.get('status','').upper()}]"
        for name, info in interpreted.items()
        if info.get("is_critical")
    ]
    severe_params = [
        f"{name} = {info['value']} {info.get('unit','')} [{info.get('status','').upper()}, {info.get('severity','')}]"
        for name, info in interpreted.items()
        if info.get("severity") in ("severe", "moderate") and not info.get("is_critical")
    ]

    urgency = context.get("urgency", "routine")
    risk_score = risk.get("score", 0)
    patterns_str = "\n  ".join(patterns) if patterns else "  None"
    critical_str = "\n  ".join(critical_params) if critical_params else "  None"
    severe_str = "\n  ".join(severe_params) if severe_params else "  None"
    age = patient_info.get("Age", "Unknown")
    gender = patient_info.get("Gender", "Unknown")

    from langchain_core.output_parsers import PydanticOutputParser
    parser = PydanticOutputParser(pydantic_object=RecsOutput)

    prompt = f"""You are a clinical AI generating personalised, actionable health recommendations
based on a patient's medical laboratory test results.
The panel may be CBC, LFT, KFT, Lipid, Thyroid, Diabetes, Coagulation, Iron, Electrolytes, or a comprehensive/mixed panel. Base recommendations on the ACTUAL findings provided — do not assume CBC-only context.

═══════════════════════════════════════
PATIENT CONTEXT
═══════════════════════════════════════
Age: {age} | Gender: {gender}
Risk Score: {risk_score}/10 | Urgency: {urgency.upper()}

═══════════════════════════════════════
CRITICAL VALUE ALERTS (immediate attention needed)
═══════════════════════════════════════
  {critical_str}

═══════════════════════════════════════
SEVERE / MODERATE ABNORMALITIES
═══════════════════════════════════════
  {severe_str}

═══════════════════════════════════════
CLINICAL PATTERNS
═══════════════════════════════════════
  {patterns_str}

═══════════════════════════════════════
SYNTHESIS SUMMARY
═══════════════════════════════════════
{synthesis[:1500]}

═══════════════════════════════════════
RECOMMENDATION RULES (MANDATORY)
═══════════════════════════════════════

PRIORITY LEVELS — assign in this order:
1. 'critical'   → Any critical alert parameter. Recommend immediate medical evaluation.
                   Example: "Go to an emergency room or call your doctor immediately."
2. 'urgent'     → Risk score ≥7, urgency='urgent', or urgency='prompt'. Recommend seeing a doctor within 24-48 hours.
3. 'follow-up'  → Moderate abnormalities, urgency='follow-up', or specific lab retests. Recommend within 1-4 weeks.
4. 'lifestyle'  → Diet, hydration, exercise, sleep, supplement guidance relevant to findings.

SPECIFICITY RULES:
- Each recommendation must reference the SPECIFIC abnormal finding it addresses.
- Do NOT give generic advice like "eat healthy" without tying it to a specific pattern.
- CBC: Low Hemoglobin/Iron → iron-rich foods + Vitamin C. High WBC → physician referral. Low Platelets → avoid NSAIDs/aspirin.
- LFT: High ALT/AST → avoid alcohol, hepatotoxic drugs; evaluate cause. Low Albumin → nutritional assessment.
- KFT: High Creatinine/Urea → hydration, nephrology referral. High Uric Acid → low-purine diet, hydration.
- Lipid: High LDL → reduce saturated fat, increase soluble fibre; statin discussion with doctor. Low HDL → exercise.
- Thyroid: High TSH → endocrinology referral; avoid self-medicating with supplements.
- Diabetes: High FBS/HbA1c → dietary consult, glycaemic monitoring, physician review.
- Coagulation: Abnormal PT/INR → medication review (anticoagulants), haematology referral.
- Electrolytes: Critical Potassium/Sodium → immediate medical evaluation — do NOT self-supplement.
- Always end critical/urgent recommendations with "consult your doctor."

SAFETY RULES:
- Do NOT recommend specific medications or dosages.
- Do NOT make definitive diagnoses.
- Always advise professional consultation for any abnormal findings.
- Lifestyle recommendations are supplementary, not replacements for medical care.

Generate 4-7 recommendations, most critical first.

{parser.get_format_instructions()}
"""

    # Medical persona + strict JSON-only reinforcement. PydanticOutputParser
    # below requires valid JSON; the base medical prompt can nudge the 70B
    # model toward prose, so we override for this task.
    recs_system = (
        MEDICAL_SYSTEM_PROMPT
        + "\n\n"
        + "TASK-SPECIFIC OUTPUT RULES (override any conflicting guidance above):\n"
        + "- Output must match the exact JSON schema given in the user message.\n"
        + "- Do NOT add commentary or explanations outside the JSON object.\n"
        + "- Your entire response must start with '{' and end with '}'.\n"
        + "- Each recommendation's 'action' and 'reason' fields carry the prose — never put prose outside the JSON."
    )
    messages = [
        SystemMessage(content=recs_system),
        HumanMessage(content=prompt),
    ]

    try:
        llm = get_llm(max_tokens=1000)
        response = llm.invoke(messages)
        parsed = parser.invoke(response)

        # Flatten to list of strings for backward compatibility with frontend
        rec_strings = [
            f"[{r.priority.upper()}] {r.action} ({r.reason})"
            for r in parsed.recommendations
        ]
        logger.info(f"recommendations: {len(rec_strings)} generated, urgency={urgency}")
        return {"recommendations": rec_strings}

    except Exception as e:
        logger.exception(f"recommendations primary model failed: {type(e).__name__}: {e}. Trying fallback.")
        try:
            llm = get_fallback_llm(max_tokens=1000)
            response = llm.invoke(messages)
            parsed = parser.invoke(response)
            rec_strings = [
                f"[{r.priority.upper()}] {r.action} ({r.reason})"
                for r in parsed.recommendations
            ]
            return {"recommendations": rec_strings}
        except Exception as e2:
            logger.exception(f"recommendations: fallback also failed: {type(e2).__name__}: {e2}")
            return {
                "recommendations": [],
                "errors": errors + [f"Recommendations Node failed: {str(e2)}"],
            }
