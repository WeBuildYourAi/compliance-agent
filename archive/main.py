"""
FastAPI application for Compliance Agent
Container-ready deployment with health checks and API endpoints
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4
import logging
import asyncio

from src.compliance_workflow import ComplianceAgentState, compliance_agent_graph
from src.config import config
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Compliance Agent API",
    description="LangGraph-powered compliance assessment and risk analysis",
    version="1.0.0"
)

# Request/Response Models
class ComplianceAssessmentRequest(BaseModel):
    user_prompt: str = Field(..., description="Compliance assessment request description")
    user_id: str = Field(default_factory=lambda: str(uuid4()), description="User identifier")
    client_id: str = Field(default_factory=lambda: str(uuid4()), description="Client identifier")
    industry_sector: Optional[str] = Field(None, description="Industry sector (optional)")
    organization_size: Optional[str] = Field(None, description="Organization size (optional)")
    geographic_scope: List[str] = Field(default_factory=list, description="Geographic scope")

class ComplianceAssessmentResponse(BaseModel):
    request_id: str
    status: str
    current_stage: str
    executive_summary: Dict[str, Any]
    action_items: List[Dict[str, Any]]
    compliance_report: Dict[str, Any]
    processing_time_seconds: float

class HealthCheckResponse(BaseModel):
    status: str
    version: str
    environment: str
    timestamp: str
    services: Dict[str, str]

# In-memory storage for demo (use proper database in production)
assessment_results = {}

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint for container orchestration"""
    
    services_status = {}
    
    # Check OpenAI API key
    services_status["openai"] = "available" if config.openai_api_key else "missing_key"
    
    # Check Perplexity API key  
    services_status["perplexity"] = "available" if config.perplexity_api_key else "optional_missing"
    
    # Check LangSmith
    services_status["langsmith"] = "enabled" if config.langchain_tracing else "disabled"
    
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        environment=config.environment,
        timestamp=datetime.utcnow().isoformat(),
        services=services_status
    )

@app.post("/assess", response_model=ComplianceAssessmentResponse)
async def create_compliance_assessment(
    request: ComplianceAssessmentRequest,
    background_tasks: BackgroundTasks
):
    """Create a new compliance assessment"""
    
    request_id = str(uuid4())
    start_time = datetime.utcnow()
    
    logger.info(f"Starting compliance assessment {request_id}")
    
    try:
        # Create initial state
        initial_state = ComplianceAgentState(
            request_id=request_id,
            user_prompt=request.user_prompt,
            user_id=request.user_id,
            client_id=request.client_id,
            correlation_id=str(uuid4()),
            compliance_frameworks=[],
            compliance_category=None,
            industry_sector=request.industry_sector,
            organization_size=request.organization_size,
            geographic_scope=request.geographic_scope,
            risk_analysis={},
            identified_risks=[],
            compliance_gaps=[],
            control_recommendations=[],
            implementation_plan={},
            status="initiated",
            current_stage="start",
            requires_user_input=False,
            user_questions=[],
            user_responses={},
            compliance_report={},
            executive_summary={},
            action_items=[],
            messages=[HumanMessage(content=f"Starting compliance assessment: {request.user_prompt}")],
            created_at=start_time,
            updated_at=start_time
        )
        
        # Store initial state
        assessment_results[request_id] = initial_state
        
        # Run the compliance agent workflow
        graph = compliance_agent_graph.compile()
        final_state = await graph.ainvoke(initial_state)
        
        # Update stored results
        assessment_results[request_id] = final_state
        
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        logger.info(f"Completed compliance assessment {request_id} in {processing_time:.2f}s")
        
        return ComplianceAssessmentResponse(
            request_id=request_id,
            status=final_state.get("status", "completed"),
            current_stage=final_state.get("current_stage", "finished"),
            executive_summary=final_state.get("executive_summary", {}),
            action_items=final_state.get("action_items", []),
            compliance_report=final_state.get("compliance_report", {}),
            processing_time_seconds=processing_time
        )
        
    except Exception as e:
        logger.error(f"Assessment {request_id} failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Compliance assessment failed: {str(e)}"
        )

@app.get("/assess/{request_id}")
async def get_assessment_results(request_id: str):
    """Get results of a specific compliance assessment"""
    
    if request_id not in assessment_results:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment {request_id} not found"
        )
    
    result = assessment_results[request_id]
    
    return {
        "request_id": request_id,
        "status": result.get("status", "unknown"),
        "current_stage": result.get("current_stage", "unknown"),
        "executive_summary": result.get("executive_summary", {}),
        "action_items": result.get("action_items", []),
        "compliance_report": result.get("compliance_report", {}),
        "created_at": result.get("created_at", datetime.utcnow()).isoformat(),
        "updated_at": result.get("updated_at", datetime.utcnow()).isoformat()
    }

@app.get("/assess")
async def list_assessments():
    """List all compliance assessments"""
    
    assessments = []
    for request_id, state in assessment_results.items():
        assessments.append({
            "request_id": request_id,
            "status": state.get("status", "unknown"),
            "current_stage": state.get("current_stage", "unknown"),
            "user_prompt": state.get("user_prompt", "")[:100] + "..." if len(state.get("user_prompt", "")) > 100 else state.get("user_prompt", ""),
            "created_at": state.get("created_at", datetime.utcnow()).isoformat(),
            "updated_at": state.get("updated_at", datetime.utcnow()).isoformat()
        })
    
    return {"assessments": assessments, "total": len(assessments)}

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "Compliance Agent API",
        "version": "1.0.0",
        "description": "LangGraph-powered compliance assessment and risk analysis",
        "endpoints": {
            "health": "/health",
            "assess": "/assess",
            "get_assessment": "/assess/{request_id}",
            "list_assessments": "/assess"
        },
        "models": {
            "gpt_mini": config.gpt_mini_model,
            "gpt_standard": config.gpt_standard_model,
            "perplexity": config.perplexity_model
        }
    }

if __name__ == "__main__":
    import uvicorn
    
    # Run the FastAPI app
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=config.environment == "development",
        log_level=config.log_level.lower()
    )
