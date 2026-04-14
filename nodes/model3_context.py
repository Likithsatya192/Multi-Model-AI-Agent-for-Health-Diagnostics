import logging
from pydantic import BaseModel, Field
from utils.llm_utils import get_llm, get_fallback_llm

logger = logging.getLogger(__name__)


class ContextOutput(BaseModel):
    analysis: str = Field(
        description=(
            "Clinical contextual analysis: how patient age, gender, and identified "
            "patterns interact. Include physiological reasoning. 4-8 sentences."
        )
    )
    adjusted_concerns: str = Field(
        description=(
            "Concerns AMPLIFIED or MITIGATED by patient context. "
            "E.g. low Hgb is more concerning in a pregnant female than an elderly male. "
            "List only findings where context changes clinical weight."
        )
    )
    urgency: str = Field(
        description=(
            "Overall urgency level: 'routine' | 'follow-up' | 'prompt' | 'urgent'. "
            "'routine' = no concerning findings. "
            "'follow-up' = mild abnormalities, recheck in 4-8 weeks. "
            "'prompt' = moderate concern, see doctor within 1 week. "
            "'urgent' = critical values, see doctor immediately."
        )
    )


def model3_context_node(state):
    """
    Node: Contextual clinical analysis.
    Uses patient demographics + param flags + identified patterns to produce
    age/gender-adjusted interpretation with urgency level.
    """
    patient_info = state.patient_info or {}
    validated = state.validated_params or {}
    patterns = state.patterns or []
    interpreted = state.param_interpretation or {}

    if not validated:
        logger.warning("model3_context: no validated params, skipping")
        return {"context_analysis": {"analysis": "No validated data.", "adjusted_concerns": "", "urgency": "routine"}}

    age = patient_info.get("Age", "Unknown")
    gender = patient_info.get("Gender", "Unknown")

    # Build detailed param summary with flags and severity
    param_lines = []
    critical_params = []
    abnormal_params = []

    for k, v in interpreted.items():
        status = v.get("status", "unknown").upper()
        severity = v.get("severity", "unknown")
        dev = v.get("deviation_pct")
        dev_str = f" ({dev:+.1f}% from mid)" if dev is not None else ""
        line = f"  {k}: {v['value']} {v.get('unit','')} [{status}] severity={severity}{dev_str}"
        param_lines.append(line)
        if v.get("is_critical"):
            critical_params.append(k)
        elif status in ("LOW", "HIGH"):
            abnormal_params.append(k)

    params_str = "\n".join(param_lines) if param_lines else "  None"
    patterns_str = "\n  ".join(patterns) if patterns else "  No patterns identified"
    critical_str = ", ".join(critical_params) if critical_params else "None"

    from langchain_core.output_parsers import PydanticOutputParser
    parser = PydanticOutputParser(pydantic_object=ContextOutput)

    prompt = f"""You are a clinical hematologist AI providing contextual analysis of a CBC blood report.
Your analysis MUST be grounded in the specific patient demographics and lab values provided.
Do NOT give generic advice. Every statement must reference the actual data below.

═══════════════════════════════════════
PATIENT DEMOGRAPHICS
═══════════════════════════════════════
Age    : {age}
Gender : {gender}

═══════════════════════════════════════
CBC RESULTS WITH CLINICAL FLAGS
═══════════════════════════════════════
{params_str}

═══════════════════════════════════════
IDENTIFIED CLINICAL PATTERNS
═══════════════════════════════════════
  {patterns_str}

═══════════════════════════════════════
CRITICAL VALUE ALERTS
═══════════════════════════════════════
  {critical_str}

═══════════════════════════════════════
CLINICAL CONTEXT RULES
═══════════════════════════════════════

AGE-SPECIFIC ADJUSTMENTS:
- Pediatric (<18 yrs): Reference ranges differ significantly. Leukocytosis is common with infection.
  Lower Hgb thresholds. Platelet values trend higher.
- Reproductive-age female (18-45 F): LOW Hemoglobin/Iron pattern — consider menstrual loss,
  pregnancy status. Iron deficiency anemia is most common cause.
- Elderly (>65): Mild anemia is common but still warrants evaluation.
  Thrombocytopenia risk with age. WBC interpretation needs baseline context.

GENDER-SPECIFIC ADJUSTMENTS:
- Male: Hemoglobin normal range is higher (13.5-17.5 g/dL). PCV accordingly higher.
- Female: Hemoglobin 12.0-15.5 g/dL. Estrogen affects platelet function.
- Unknown gender: Note that reference ranges and clinical significance may vary.

URGENCY CRITERIA:
- 'urgent'     → Any CRITICAL value, or ≥2 severe abnormalities, or pancytopenia
- 'prompt'     → Any severe abnormality, or patterns suggesting active disease
- 'follow-up'  → Mild-moderate isolated abnormalities
- 'routine'    → All within normal limits or borderline mild

═══════════════════════════════════════
TASK
═══════════════════════════════════════
1. Write a contextual analysis explaining how this patient's age and gender influence
   interpretation of the detected patterns.
2. Identify which findings are amplified or mitigated by demographic context.
3. Assign the appropriate urgency level with clear justification.

{parser.get_format_instructions()}
"""

    try:
        llm = get_llm(max_tokens=900)
        response = llm.invoke(prompt)
        parsed = parser.invoke(response)
        result = {
            "analysis": parsed.analysis,
            "adjusted_concerns": parsed.adjusted_concerns,
            "urgency": parsed.urgency,
        }
        logger.info(f"model3_context: urgency={parsed.urgency}, critical_params={critical_params}")
        return {"context_analysis": result}

    except Exception as e:
        logger.warning(f"model3_context primary model failed: {e}. Trying fallback.")
        try:
            llm = get_fallback_llm(max_tokens=900)
            response = llm.invoke(prompt)
            parsed = parser.invoke(response)
            return {
                "context_analysis": {
                    "analysis": parsed.analysis,
                    "adjusted_concerns": parsed.adjusted_concerns,
                    "urgency": parsed.urgency,
                }
            }
        except Exception as e2:
            logger.error(f"model3_context fallback also failed: {e2}")
            return {"errors": state.errors + [f"Model 3 (Context) failed: {str(e2)}"]}
