from typing import List
from pydantic import BaseModel, Field
from utils.llm_utils import get_llm

class RecsOutput(BaseModel):
    recommendations: List[str] = Field(description="List of actionable health recommendations")

def recommendations_node(state):
    """
    Generates personalized recommendations based on the synthesized findings.
    """
    synthesis = state.synthesis_report
    if not synthesis:
        return {"recommendations": []}

    llm = get_llm()
    # structured_llm = llm.with_structured_output(RecsOutput)
    from langchain_core.output_parsers import PydanticOutputParser
    parser = PydanticOutputParser(pydantic_object=RecsOutput)
    
    prompt = f"""
    Based on the following medical report summary:
    
    "{synthesis}"
    
    Provide 3-5 actionable health, diet, or lifestyle recommendations.
    Be specific but safe (always advise consulting a doctor).
    
    {parser.get_format_instructions()}
    """
    
    try:
        response = llm.invoke(prompt)
        parsed = parser.invoke(response)
        return {"recommendations": parsed.recommendations}
    except Exception as e:
        return {"errors": state.errors + [f"Recommendations Node failed: {str(e)}"]}
