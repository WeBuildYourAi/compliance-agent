"""
Enhanced Compliance Agent Workflow - Project Planning & Multi-Document Orchestration
Production-ready implementation for complex compliance projects with parallel document generation
"""
import sys
import os
from pathlib import Path

# Add the src directory to Python path for imports
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from typing import Dict, Any, List, Optional, TypedDict, Literal, Annotated
from enum import Enum
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from datetime import datetime
import logging
import uuid
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Import utilities - now using absolute imports from current directory
from llm_utils import llm_manager
from config import config
from storage_utils import storage_manager, cosmos_manager

# Configure logging for LangGraph Platform
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enhanced Compliance Framework Support
class ComplianceFramework(str, Enum):
    GDPR = "gdpr"
    SOX = "sox"
    HIPAA = "hipaa"
    CCPA = "ccpa"
    PCI_DSS = "pci_dss"
    ISO_27001 = "iso_27001"
    NIST = "nist"
    SOC2 = "soc2"
    FERPA = "ferpa"
    GLBA = "glba"
    PIPEDA = "pipeda"
    LGPD = "lgpd"

class ProjectType(str, Enum):
    PRIVACY_POLICY_PACK = "privacy_policy_pack"
    COMPLIANCE_ASSESSMENT = "compliance_assessment"
    AUDIT_PREPARATION = "audit_preparation"
    RISK_ANALYSIS = "risk_analysis"
    POLICY_REVIEW = "policy_review"
    IMPLEMENTATION_PLAN = "implementation_plan"
    MULTI_DOCUMENT_PACK = "multi_document_pack"

class DocumentType(str, Enum):
    PRIVACY_POLICY = "privacy_policy"
    PRIVACY_NOTICE = "privacy_notice"
    ROPA = "ropa"
    DPIA = "dpia"
    DSAR_WORKFLOW = "dsar_workflow"
    COOKIE_POLICY = "cookie_policy"
    DPA_TEMPLATE = "dpa_template"
    BREACH_RESPONSE = "breach_response"
    VENDOR_ASSESSMENT = "vendor_assessment"
    COMPLIANCE_CHECKLIST = "compliance_checklist"
    TRAINING_MATERIALS = "training_materials"
    AUDIT_REPORT = "audit_report"

class DocumentStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"

class AssessmentStatus(str, Enum):
    INITIATED = "initiated"
    ANALYZING_PROJECT = "analyzing_project"
    PLANNING_DOCUMENTS = "planning_documents"
    GENERATING_DOCUMENTS = "generating_documents"
    CONSOLIDATING_RESULTS = "consolidating_results"
    COMPLETED = "completed"
    FAILED = "failed"

# Enhanced State Definition for Multi-Document Projects
class ComplianceAgentState(TypedDict):
    # Core Input - now supports complex project plans
    user_prompt: str
    project_plan: Optional[Dict[str, Any]]  # Structured project input
    deliverable_blueprint: Optional[List[Dict[str, Any]]]  # Detailed deliverable specifications from content-orchestrator
    request_id: str
    
    # New fields from research synthesis and user interaction
    user_responses: Optional[Dict[str, Any]]  # User's answers to the questions
    interaction_questions: Optional[List[Dict[str, Any]]]  # The actual questions that were asked (for full context)
    project_brief: Optional[Dict[str, Any]]  # Enhanced with research insights
    
    # Session Management
    user_id: Optional[str]
    session_id: Optional[str]
    correlation_id: str
    
    # Project Analysis
    project_type: Optional[ProjectType]
    identified_frameworks: List[ComplianceFramework]
    project_complexity: str
    estimated_duration: Optional[str]
    required_documents: List[Dict[str, Any]]
    
    # Document Orchestration
    document_plans: List[Dict[str, Any]]
    document_results: Dict[str, Dict[str, Any]]
    document_status: Dict[str, DocumentStatus]
    parallel_execution: bool
    
    # Traditional Assessment Results (for single assessments)
    compliance_category: Optional[str]
    industry_sector: Optional[str]
    organization_size: Optional[str]
    geographic_scope: List[str]
    risk_analysis: Dict[str, Any]
    identified_risks: List[Dict[str, Any]]
    compliance_gaps: List[Dict[str, Any]]
    control_recommendations: List[Dict[str, Any]]
    implementation_plan: Dict[str, Any]
    
    # Workflow State Management
    status: AssessmentStatus
    current_stage: str
    error_message: Optional[str]
    retry_count: int
    
    # LangSmith Integration
    run_id: Optional[str]
    trace_data: Dict[str, Any]
    
    # Output
    executive_summary: Dict[str, Any]
    action_items: List[Dict[str, Any]]
    compliance_report: Dict[str, Any]
    project_deliverables: Dict[str, Any]
    
    # Message History for LangSmith
    messages: Annotated[List[BaseMessage], "Message history for conversation tracking"]
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    processing_duration: Optional[float]

def ensure_state_initialization(state: ComplianceAgentState) -> ComplianceAgentState:
    """Ensure all required state fields are initialized"""
    # Core message and data structures
    if "messages" not in state or state["messages"] is None:
        state["messages"] = []
    if "trace_data" not in state or state["trace_data"] is None:
        state["trace_data"] = {}
    if "document_results" not in state or state["document_results"] is None:
        state["document_results"] = {}
    if "document_status" not in state or state["document_status"] is None:
        state["document_status"] = {}
    
    # New fields from research synthesis and user interaction
    if "user_responses" not in state or state["user_responses"] is None:
        state["user_responses"] = {}
    if "interaction_questions" not in state or state["interaction_questions"] is None:
        state["interaction_questions"] = []
    if "project_brief" not in state or state["project_brief"] is None:
        state["project_brief"] = {}
    if "deliverable_blueprint" not in state or state["deliverable_blueprint"] is None:
        state["deliverable_blueprint"] = []
    
    # Other core fields that might be missing
    if "identified_frameworks" not in state or state["identified_frameworks"] is None:
        state["identified_frameworks"] = []
    if "geographic_scope" not in state or state["geographic_scope"] is None:
        state["geographic_scope"] = []
    if "required_documents" not in state or state["required_documents"] is None:
        state["required_documents"] = []
    if "document_plans" not in state or state["document_plans"] is None:
        state["document_plans"] = []
    if "risk_analysis" not in state or state["risk_analysis"] is None:
        state["risk_analysis"] = {}
    if "identified_risks" not in state or state["identified_risks"] is None:
        state["identified_risks"] = []
    if "compliance_gaps" not in state or state["compliance_gaps"] is None:
        state["compliance_gaps"] = []
    if "control_recommendations" not in state or state["control_recommendations"] is None:
        state["control_recommendations"] = []
    if "implementation_plan" not in state or state["implementation_plan"] is None:
        state["implementation_plan"] = {}
    if "executive_summary" not in state or state["executive_summary"] is None:
        state["executive_summary"] = {}
    if "action_items" not in state or state["action_items"] is None:
        state["action_items"] = []
    if "compliance_report" not in state or state["compliance_report"] is None:
        state["compliance_report"] = {}
    if "project_deliverables" not in state or state["project_deliverables"] is None:
        state["project_deliverables"] = {}
    
    return state

def add_trace_data(state: ComplianceAgentState, stage: str, data: Dict[str, Any]) -> ComplianceAgentState:
    """Add trace data for LangSmith monitoring"""
    if "trace_data" not in state:
        state["trace_data"] = {}
    
    state["trace_data"][stage] = {
        "timestamp": datetime.utcnow().isoformat(),
        "data": data,
        "stage": stage
    }
    
    return state

def handle_node_error(state: ComplianceAgentState, error: Exception, node_name: str) -> ComplianceAgentState:
    """Centralized error handling for all nodes"""
    logger.error(f"Error in {node_name}: {error}", exc_info=True)
    
    # Ensure state is properly initialized
    state = ensure_state_initialization(state)
    
    state["error_message"] = f"{node_name} failed: {str(error)}"
    state["retry_count"] = state.get("retry_count", 0) + 1
    state["updated_at"] = datetime.utcnow()
    
    # Add error to trace data
    state = add_trace_data(state, f"{node_name}_error", {
        "error": str(error),
        "retry_count": state["retry_count"]
    })
    
    # Add error message to conversation
    state["messages"].append(AIMessage(
        content=f"Processing error in {node_name}. Retry attempt {state['retry_count']}/3."
    ))
    
    return state

def _map_blueprint_to_document_type(title: str) -> str:
    """Map deliverable blueprint title to DocumentType"""
    title_lower = title.lower()
    
    if "privacy policy" in title_lower or "data protection policy" in title_lower:
        return "privacy_policy"
    elif "privacy notice" in title_lower or "privacy statement" in title_lower:
        return "privacy_notice"
    elif "ropa" in title_lower or "records of processing" in title_lower:
        return "ropa"
    elif "dpia" in title_lower or "data protection impact" in title_lower:
        return "dpia"
    elif "dsar" in title_lower or "data subject access" in title_lower:
        return "dsar_workflow"
    elif "cookie" in title_lower:
        return "cookie_policy"
    elif "dpa" in title_lower or "data processing agreement" in title_lower:
        return "dpa_template"
    elif "breach" in title_lower:
        return "breach_response"
    elif "vendor" in title_lower or "processor" in title_lower:
        return "vendor_assessment"
    elif "training" in title_lower:
        return "training_materials"
    elif "audit" in title_lower or "compliance checklist" in title_lower:
        return "compliance_checklist"
    else:
        return "compliance_checklist"  # Default

def _extract_target_audience(description: str) -> str:
    """Extract target audience from blueprint description"""
    description_lower = description.lower()
    
    if "legal" in description_lower or "counsel" in description_lower:
        return "legal"
    elif "technical" in description_lower or "engineering" in description_lower:
        return "technical"
    elif "executive" in description_lower or "c-suite" in description_lower:
        return "executive"
    elif "customer" in description_lower or "public" in description_lower:
        return "end_users"
    elif "auditor" in description_lower or "compliance" in description_lower:
        return "auditors"
    else:
        return "legal"  # Default to legal for compliance documents

# Enhanced Node Functions
async def analyze_project_requirements(state: ComplianceAgentState) -> ComplianceAgentState:
    """Analyze incoming project plan and deliverable blueprint from content-orchestrator"""
    
    try:
        logger.info(f"Analyzing project requirements for request: {state.get('request_id')}")
        logger.info(f"Available data - user_responses: {len(user_responses)} items, interaction_questions: {len(interaction_questions)} items, project_brief: {'enhanced' if project_brief else 'basic'}, deliverable_blueprint: {len(deliverable_blueprint)} items")
        
        # Ensure state is properly initialized
        state = ensure_state_initialization(state)
        
        # Update status
        state["status"] = AssessmentStatus.ANALYZING_PROJECT
        state["current_stage"] = "project_analysis"
        state["updated_at"] = datetime.utcnow()
        
        user_prompt = state.get("user_prompt", "")
        project_plan = state.get("project_plan", {})
        deliverable_blueprint = state.get("deliverable_blueprint", [])
        user_responses = state.get("user_responses", {})
        interaction_questions = state.get("interaction_questions", [])
        project_brief = state.get("project_brief", {})
        
        if not user_prompt.strip():
            raise ValueError("User prompt cannot be empty")
        
        logger.info(f"Available context - user_responses: {len(user_responses)} items, interaction_questions: {len(interaction_questions)} items, project_brief: {'enhanced' if project_brief else 'basic'}, deliverable_blueprint: {len(deliverable_blueprint)} items")
        
        # If we have a deliverable blueprint from content-orchestrator, use it directly
        if deliverable_blueprint:
            logger.info(f"Using deliverable blueprint from content-orchestrator with {len(deliverable_blueprint)} specified deliverables")
            
            # Extract project details from the blueprint structure
            project_type = ProjectType.MULTI_DOCUMENT_PACK  # Since we have multiple specific deliverables
            identified_frameworks = [ComplianceFramework.GDPR]  # Default, could be extracted from blueprint
            
            # Convert blueprint to required_documents format
            required_documents = []
            for i, blueprint_item in enumerate(deliverable_blueprint):
                # Map blueprint to document requirement format
                doc_req = {
                    "document_type": _map_blueprint_to_document_type(blueprint_item.get("title", "")),
                    "document_title": blueprint_item.get("title", f"Document {i+1}"),
                    "priority": "critical" if "policy" in blueprint_item.get("title", "").lower() else "high",
                    "complexity": "high",  # Assume high for detailed blueprints
                    "estimated_effort": "high",
                    "dependencies": [],
                    "frameworks_applicable": ["gdpr"],  # Could extract from blueprint
                    "target_audience": _extract_target_audience(blueprint_item.get("description", "")),
                    "format_requirements": blueprint_item.get("format", "html"),
                    "length_estimate": "comprehensive",
                    "special_requirements": blueprint_item.get("description", ""),
                    "quality_requirements": blueprint_item.get("quality_requirements", []),
                    "blueprint_specification": blueprint_item  # Keep original blueprint for reference
                }
                required_documents.append(doc_req)
            
            # Update state with extracted information
            state["project_type"] = project_type
            state["identified_frameworks"] = [identified_frameworks] if isinstance(identified_frameworks, ComplianceFramework) else identified_frameworks
            state["project_complexity"] = "very_high"  # Detailed blueprints are complex
            state["estimated_duration"] = "3-6 months"
            state["parallel_execution"] = len(required_documents) > 3  # Parallel for many docs
            state["required_documents"] = required_documents
            
            # Extract additional context from project_brief (enhanced with research insights)
            if project_brief:
                state["industry_sector"] = project_brief.get("industry_sector", project_plan.get("industry_sector", "not_specified"))
                state["organization_size"] = project_brief.get("organization_size", project_plan.get("organization_size", "not_specified"))
                state["geographic_scope"] = project_brief.get("geographic_scope", project_plan.get("geographic_scope", []))
                
                # Extract compliance context from research insights
                if "compliance_context" in project_brief:
                    compliance_context = project_brief["compliance_context"]
                    if "frameworks" in compliance_context:
                        # Override or enhance frameworks based on research
                        research_frameworks = []
                        for fw in compliance_context["frameworks"]:
                            try:
                                research_frameworks.append(ComplianceFramework(fw.lower().replace("-", "_")))
                            except ValueError:
                                logger.warning(f"Unknown framework from research: {fw}")
                        if research_frameworks:
                            identified_frameworks = research_frameworks
            elif project_plan:
                state["industry_sector"] = project_plan.get("industry_sector", "not_specified")
                state["organization_size"] = project_plan.get("organization_size", "not_specified")
                state["geographic_scope"] = project_plan.get("geographic_scope", [])
            
            state["messages"].append(AIMessage(
                content=f"Project analysis complete using content-orchestrator blueprint: {len(required_documents)} specialized deliverables identified."
            ))
            
        else:
            # Fallback to original analysis if no blueprint provided
            logger.info("No deliverable blueprint provided, performing standard project analysis")
            
            llm = llm_manager.get_standard_llm()
            
            # [Keep original project analysis logic here as fallback]
            project_analysis_prompt = f"""
            You are a compliance project analyst. Analyze the following compliance request and available context to determine the scope, complexity, and required deliverables.

            USER REQUEST: {user_prompt}
            
            PROJECT PLAN: {json.dumps(project_plan, indent=2) if project_plan else "No structured project plan provided"}
            
            PROJECT BRIEF (with research insights): {json.dumps(project_brief, indent=2) if project_brief else "No enhanced project brief available"}
            
            USER RESPONSES TO QUESTIONS: {json.dumps(user_responses, indent=2) if user_responses else "No user responses available"}
            
            INTERACTION QUESTIONS ASKED: {json.dumps(interaction_questions, indent=2) if interaction_questions else "No interaction questions available"}
            
            Based on this comprehensive context, provide a detailed project analysis in JSON format:
            {{
                "project_type": "compliance_assessment|privacy_policy_pack|audit_preparation|risk_analysis|policy_review|implementation_plan|multi_document_pack",
                "identified_frameworks": ["gdpr", "sox", "hipaa", "ccpa", "pci_dss", "iso_27001", "nist", "soc2"],
                "project_complexity": "low|medium|high|very_high",
                "estimated_duration": "1-2 weeks|2-4 weeks|1-3 months|3-6 months|6+ months",
                "parallel_execution_suitable": true,
                "required_documents": [
                    {{
                        "document_type": "privacy_policy|compliance_checklist|dpia|ropa|training_materials|audit_report",
                        "document_title": "Document Title",
                        "priority": "critical|high|medium|low",
                        "complexity": "low|medium|high",
                        "estimated_effort": "low|medium|high",
                        "target_audience": "legal|technical|executive|end_users|auditors",
                        "frameworks_applicable": ["gdpr", "sox"]
                    }}
                ],
                "industry_context": "extracted from user responses and project brief",
                "organization_context": "size and structure context",
                "geographic_context": ["regions or countries"]
            }}
            
            ANALYSIS REQUIREMENTS:
            1. Prioritize information from the project_brief as it contains research insights
            2. Use user_responses to understand specific organizational needs and constraints
            3. Consider interaction_questions to understand what areas were explored
            4. Determine appropriate compliance frameworks based on industry, geography, and user responses
            5. Plan document complexity and effort based on organizational size and technical capability
            """
            
            # Execute fallback analysis
            analysis_result = await llm_manager.safe_llm_query(llm, project_analysis_prompt, parse_json=True)
            
            if "error" not in analysis_result:
                # Process fallback results
                project_type = ProjectType(analysis_result.get("project_type", "compliance_assessment"))
                identified_frameworks = [ComplianceFramework(fw) for fw in analysis_result.get("identified_frameworks", [])]
                
                # Update state with fallback results
                state["project_type"] = project_type
                state["identified_frameworks"] = identified_frameworks
                state["project_complexity"] = analysis_result.get("project_complexity", "medium")
                state["estimated_duration"] = analysis_result.get("estimated_duration")
                state["parallel_execution"] = analysis_result.get("parallel_execution_suitable", False)
                state["required_documents"] = analysis_result.get("required_documents", [])
                
                state["messages"].append(AIMessage(
                    content=f"Project analysis complete using fallback logic: {project_type.value} with {len(identified_frameworks)} frameworks."
                ))
            else:
                # Ultimate fallback
                state["project_type"] = ProjectType.COMPLIANCE_ASSESSMENT
                state["identified_frameworks"] = [ComplianceFramework.GDPR]
                state["project_complexity"] = "medium"
                state["required_documents"] = [{"document_type": "compliance_checklist", "document_title": "Basic Assessment"}]
        
        state["status"] = AssessmentStatus.PLANNING_DOCUMENTS
        return state
        
    except Exception as e:
        return handle_node_error(state, e, "analyze_project_requirements")

async def create_document_plans(state: ComplianceAgentState) -> ComplianceAgentState:
    """Create detailed execution plans for each required document"""
    
    try:
        logger.info("Creating detailed document execution plans")
        
        # Ensure state is properly initialized
        state = ensure_state_initialization(state)
        
        state["status"] = AssessmentStatus.PLANNING_DOCUMENTS
        state["current_stage"] = "document_planning"
        state["updated_at"] = datetime.utcnow()
        
        required_documents = state.get("required_documents", [])
        project_type = state.get("project_type")
        frameworks = state.get("identified_frameworks", [])
        
        if not required_documents:
            # Create a default document if none specified
            required_documents = [{
                "document_type": "compliance_checklist",
                "document_title": "Compliance Assessment",
                "priority": "high",
                "complexity": "medium"
            }]
        
        llm = llm_manager.get_standard_llm()
        
        document_plans = []
        
        for i, doc_req in enumerate(required_documents):
            # Create detailed plan for each document
            planning_prompt = f"""
            You are a compliance document specialist. Create a detailed execution plan for the following document requirement.

            DOCUMENT REQUIREMENT:
            {json.dumps(doc_req, indent=2)}
            
            PROJECT CONTEXT:
            - Project Type: {project_type.value if project_type else 'Unknown'}
            - Frameworks: {', '.join([f.value.upper() for f in frameworks])}
            - Industry: {state.get('industry_sector', 'Not specified')}
            - Organization Size: {state.get('organization_size', 'Not specified')}
            - Geographic Scope: {', '.join(state.get('geographic_scope', []))}
            
            USER CONTEXT (for personalization):
            - User Responses: {json.dumps(state.get('user_responses', {}), indent=2) if state.get('user_responses') else 'No user responses available'}
            - Project Brief: {json.dumps(state.get('project_brief', {}), indent=2) if state.get('project_brief') else 'No enhanced project brief available'}
            
            Create a detailed execution plan in JSON format:
            {{
                "document_id": "doc_{i+1:03d}",
                "execution_plan": {{
                    "research_requirements": [
                        "Research area 1",
                        "Research area 2"
                    ],
                    "content_sections": [
                        {{
                            "section_title": "Section Title",
                            "section_description": "What this section covers",
                            "content_type": "legal|technical|procedural|explanatory",
                            "word_count_estimate": 500,
                            "complexity": "low|medium|high"
                        }}
                    ],
                    "template_approach": "custom|standard|hybrid",
                    "validation_requirements": [
                        "Legal review required",
                        "Technical accuracy check"
                    ],
                    "format_specifications": {{
                        "primary_format": "html|pdf|word|json|csv",
                        "styling_requirements": "professional|user-friendly|technical|legal"
                    }}
                }}
            }}
            
            PLANNING REQUIREMENTS:
            1. Consider the specific document type and its compliance requirements
            2. Account for framework-specific content needs
            3. Plan for appropriate depth and technical detail
            4. Include validation and quality assurance steps
            5. Consider dependencies and sequencing
            """
            
            # Execute document planning
            planning_result = await llm_manager.safe_llm_query(llm, planning_prompt, parse_json=True)
            
            if "error" not in planning_result:
                document_plan = {
                    "document_id": f"doc_{i+1:03d}",
                    "document_requirement": doc_req,
                    "execution_plan": planning_result.get("execution_plan", {}),
                    "status": DocumentStatus.PENDING,
                    "created_at": datetime.utcnow().isoformat()
                }
                document_plans.append(document_plan)
            else:
                # Fallback plan
                document_plan = {
                    "document_id": f"doc_{i+1:03d}",
                    "document_requirement": doc_req,
                    "execution_plan": {
                        "template_approach": "standard",
                        "content_sections": [{"section_title": "Main Content", "content_type": "standard"}],
                        "format_specifications": {"primary_format": "html"}
                    },
                    "status": DocumentStatus.PENDING,
                    "created_at": datetime.utcnow().isoformat()
                }
                document_plans.append(document_plan)
        
        # Update state
        state["document_plans"] = document_plans
        state["document_status"] = {plan["document_id"]: DocumentStatus.PENDING for plan in document_plans}
        
        state["messages"].append(AIMessage(
            content=f"Document planning complete: {len(document_plans)} detailed execution plans created."
        ))
        
        state["status"] = AssessmentStatus.GENERATING_DOCUMENTS
        return state
        
    except Exception as e:
        return handle_node_error(state, e, "create_document_plans")

async def generate_single_document(document_plan: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a single document based on its execution plan"""
    
    document_id = document_plan.get("document_id")
    doc_req = document_plan.get("document_requirement", {})
    exec_plan = document_plan.get("execution_plan", {})
    
    try:
        logger.info(f"Generating document: {document_id} - {doc_req.get('document_title', 'Untitled')}")
        
        llm = llm_manager.get_standard_llm()
        
        # Enhanced document generation prompt
        generation_prompt = f"""
        You are a compliance document specialist. Generate a high-quality compliance document based on the detailed execution plan.

        DOCUMENT REQUIREMENT:
        {json.dumps(doc_req, indent=2)}
        
        EXECUTION PLAN:
        {json.dumps(exec_plan, indent=2)}
        
        PROJECT CONTEXT:
        {json.dumps(context, indent=2)}
        
        Generate the complete document content in JSON format:
        {{
            "document_metadata": {{
                "document_id": "{document_id}",
                "title": "Document Title",
                "document_type": "{doc_req.get('document_type', 'unknown')}",
                "version": "1.0",
                "created_date": "{datetime.utcnow().isoformat()}",
                "applicable_frameworks": [],
                "target_audience": "{doc_req.get('target_audience', 'general')}",
                "approval_status": "draft",
                "word_count": 0
            }},
            "document_content": {{
                "executive_summary": "Brief executive summary of the document",
                "main_sections": [
                    {{
                        "section_id": "section_1",
                        "section_title": "Section Title",
                        "section_content": "Complete section content with proper formatting and legal language",
                        "subsections": [
                            {{
                                "subsection_title": "Subsection Title",
                                "subsection_content": "Detailed content"
                            }}
                        ]
                    }}
                ],
                "appendices": [
                    {{
                        "appendix_title": "Appendix A",
                        "appendix_content": "Supporting content"
                    }}
                ],
                "footer_content": "Standard footer with disclaimers and contact information"
            }},
            "quality_metrics": {{
                "completeness_score": 0.95,
                "accuracy_score": 0.90,
                "readability_score": 0.85,
                "compliance_coverage": 0.92
            }},
            "next_steps": [
                "Review and validation step 1",
                "Review and validation step 2"
            ]
        }}
        
        GENERATION REQUIREMENTS:
        1. Create professional, legally sound content appropriate for the document type
        2. Ensure compliance with specified frameworks
        3. Use appropriate tone and language for the target audience
        4. Include all required sections based on the execution plan
        5. Provide comprehensive, actionable content
        6. Consider industry-specific requirements and best practices
        
        Focus on creating high-quality, professional content that meets enterprise compliance standards.
        """
        
        # Execute document generation
        generation_result = await llm_manager.safe_llm_query(llm, generation_prompt, parse_json=True)
        
        if "error" not in generation_result:
            return {
                "document_id": document_id,
                "status": DocumentStatus.COMPLETED,
                "content": generation_result,
                "generated_at": datetime.utcnow().isoformat(),
                "success": True
            }
        else:
            logger.error(f"Document generation failed for {document_id}: {generation_result.get('error')}")
            return {
                "document_id": document_id,
                "status": DocumentStatus.FAILED,
                "error": generation_result.get("error", "Unknown error"),
                "generated_at": datetime.utcnow().isoformat(),
                "success": False
            }
    
    except Exception as e:
        logger.error(f"Document generation exception for {document_id}: {e}")
        return {
            "document_id": document_id,
            "status": DocumentStatus.FAILED,
            "error": str(e),
            "generated_at": datetime.utcnow().isoformat(),
            "success": False
        }

async def execute_document_generation(state: ComplianceAgentState) -> ComplianceAgentState:
    """Execute document generation - parallel or sequential based on project requirements"""
    
    try:
        logger.info("Executing document generation")
        
        # Ensure state is properly initialized
        state = ensure_state_initialization(state)
        
        state["status"] = AssessmentStatus.GENERATING_DOCUMENTS
        state["current_stage"] = "document_generation"
        state["updated_at"] = datetime.utcnow()
        
        document_plans = state.get("document_plans", [])
        parallel_execution = state.get("parallel_execution", False)
        
        if not document_plans:
            raise ValueError("No document plans available for execution")
        
        # Prepare context for document generation
        generation_context = {
            "project_type": state.get("project_type", {}).value if state.get("project_type") else "unknown",
            "frameworks": [f.value for f in state.get("identified_frameworks", [])],
            "industry_sector": state.get("industry_sector"),
            "organization_size": state.get("organization_size"),
            "geographic_scope": state.get("geographic_scope", []),
            "project_complexity": state.get("project_complexity", "medium")
        }
        
        document_results = {}
        
        if parallel_execution and len(document_plans) > 1:
            # Parallel execution for suitable projects
            logger.info(f"Executing {len(document_plans)} documents in parallel")
            
            # Create async tasks for parallel execution
            tasks = [
                generate_single_document(plan, generation_context)
                for plan in document_plans
            ]
            
            # Execute all documents in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    document_id = document_plans[i].get("document_id", f"doc_{i+1:03d}")
                    document_results[document_id] = {
                        "document_id": document_id,
                        "status": DocumentStatus.FAILED,
                        "error": str(result),
                        "success": False
                    }
                else:
                    document_id = result.get("document_id")
                    document_results[document_id] = result
        
        else:
            # Sequential execution
            logger.info(f"Executing {len(document_plans)} documents sequentially")
            
            for plan in document_plans:
                document_id = plan.get("document_id")
                
                # Update status to in progress
                state["document_status"][document_id] = DocumentStatus.IN_PROGRESS
                
                # Generate document
                result = await generate_single_document(plan, generation_context)
                document_results[document_id] = result
                
                # Update status
                state["document_status"][document_id] = DocumentStatus(result.get("status", DocumentStatus.FAILED))
        
        # Update state with results
        state["document_results"] = document_results
        
        # Calculate success metrics
        total_docs = len(document_plans)
        successful_docs = len([r for r in document_results.values() if r.get("success")])
        
        state["messages"].append(AIMessage(
            content=f"Document generation complete: {successful_docs}/{total_docs} documents generated successfully."
        ))
        
        state["status"] = AssessmentStatus.CONSOLIDATING_RESULTS
        return state
        
    except Exception as e:
        return handle_node_error(state, e, "execute_document_generation")

async def consolidate_project_results(state: ComplianceAgentState) -> ComplianceAgentState:
    """Consolidate all document results and create project deliverables"""
    
    try:
        logger.info("Consolidating project results and creating deliverables")
        
        # Ensure state is properly initialized
        state = ensure_state_initialization(state)
        
        state["status"] = AssessmentStatus.CONSOLIDATING_RESULTS
        state["current_stage"] = "result_consolidation"
        state["updated_at"] = datetime.utcnow()
        
        document_results = state.get("document_results", {})
        project_type = state.get("project_type")
        frameworks = state.get("identified_frameworks", [])
        
        # Calculate final metrics
        successful_docs = len([r for r in document_results.values() if r.get("success")])
        total_docs = len(document_results)
        
        # Create final deliverables package
        project_deliverables = {
            "project_metadata": {
                "project_id": state.get("request_id"),
                "completion_date": datetime.utcnow().isoformat(),
                "total_documents": total_docs,
                "successful_documents": successful_docs,
                "success_rate": successful_docs / total_docs if total_docs > 0 else 0
            },
            "document_results": document_results,
            "executive_summary": {
                "project_scope": f"Generated {successful_docs} of {total_docs} requested documents",
                "completion_status": "completed" if successful_docs == total_docs else "partially_completed",
                "frameworks_covered": [f.value for f in frameworks],
                "next_steps": ["Review generated documents", "Implement compliance measures", "Schedule follow-up assessment"]
            }
        }
        
        # Update state
        state["project_deliverables"] = project_deliverables
        state["executive_summary"] = project_deliverables["executive_summary"]
        
        # Create action items
        action_items = [
            {
                "action_id": "action_001",
                "title": "Review Generated Documents",
                "priority": "critical",
                "timeline": "immediate"
            },
            {
                "action_id": "action_002", 
                "title": "Implement Compliance Measures",
                "priority": "high",
                "timeline": "short_term"
            }
        ]
        
        state["action_items"] = action_items
        
        # Calculate processing duration
        start_time = state.get("created_at")
        if start_time:
            processing_duration = (datetime.utcnow() - start_time).total_seconds()
            state["processing_duration"] = processing_duration
        
        state["status"] = AssessmentStatus.COMPLETED
        state["current_stage"] = "completed"
        state["updated_at"] = datetime.utcnow()
        
        state["messages"].append(AIMessage(
            content=f"Project consolidation complete! {successful_docs}/{total_docs} documents delivered successfully."
        ))
        
        logger.info(f"Project consolidation completed: {successful_docs}/{total_docs} documents")
        
        return state
        
    except Exception as e:
        return handle_node_error(state, e, "consolidate_project_results")

# Build the Complete Multi-Document Compliance Workflow
def build_compliance_graph() -> StateGraph:
    """Build the complete compliance agent workflow graph for multi-document projects"""
    
    workflow = StateGraph(ComplianceAgentState)
    
    # Add all workflow nodes
    workflow.add_node("analyze_project", analyze_project_requirements)
    workflow.add_node("plan_documents", create_document_plans)
    workflow.add_node("generate_documents", execute_document_generation)
    workflow.add_node("consolidate_results", consolidate_project_results)
    
    # Set entry point
    workflow.set_entry_point("analyze_project")
    
    # Add workflow edges to create the complete pipeline
    workflow.add_edge("analyze_project", "plan_documents")
    workflow.add_edge("plan_documents", "generate_documents")
    workflow.add_edge("generate_documents", "consolidate_results")
    workflow.add_edge("consolidate_results", END)
    
    return workflow

# Export the complete compliance agent
compliance_agent_graph = build_compliance_graph()

# Health check function for LangGraph Platform
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for LangGraph Platform monitoring"""
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0",
            "capabilities": {
                "multi_document_generation": True,
                "parallel_execution": True,
                "framework_coverage": len(ComplianceFramework),
                "supported_document_types": len(DocumentType),
                "project_types": len(ProjectType)
            },
            "workflow_stages": [
                "analyze_project",
                "plan_documents", 
                "generate_documents",
                "consolidate_results"
            ]
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
