from pydantic import BaseModel, Field
from utils.llm_utils import get_llm

class ContextOutput(BaseModel):
    analysis: str = Field(description="Contextual analysis of the results considering age/gender/lifestyle")
    adjusted_concerns: str = Field(description="Any concerns that are amplified or mitigated by context")

def model3_context_node(state):
    """
    Incorporates user context into the analysis.
    """
    # Use extracted info or fallback
    patient_info = state.patient_info or {}
    user_context = {
        "Age": patient_info.get("Age", "Unknown"), 
        "Gender": patient_info.get("Gender", "Unknown"),
        "History": "None provided"
    }

    validated = state.validated_params
    patterns = state.patterns
    
    if not validated:
        return {"context_analysis": {}}

    llm = get_llm()
    # structured_llm = llm.with_structured_output(ContextOutput)
    from langchain_core.output_parsers import PydanticOutputParser
    parser = PydanticOutputParser(pydantic_object=ContextOutput)
    
    data_str = "\n".join([f"{k}: {v['value']} {v.get('unit','')}" for k, v in validated.items()])
    patterns_str = ", ".join(patterns)

    prompt = f"""
    You are a medical AI assistant.
    User Context:
    Age: {user_context.get('Age')}
    Gender: {user_context.get('Gender')}
    Medical History: {user_context.get('History')}
    
    Lab Results:
    {data_str}
    
    Identified Patterns:
    {patterns_str}
    
    Provide a brief contextual analysis. 
    If age/gender is unknown, provide general guidance on how these factors usually influence interpretation for the identified patterns.
    
    {parser.get_format_instructions()}
    """

    try:
        response = llm.invoke(prompt)
        parsed = parser.invoke(response)
        return {
            "context_analysis": {
                "analysis": parsed.analysis,
                "adjusted_concerns": parsed.adjusted_concerns
            }
        }
    except Exception as e:
         return {"errors": state.errors + [f"Model 3 (Context) failed: {str(e)}"]}
