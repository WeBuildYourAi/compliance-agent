"""
Environment configuration for Compliance Agent
Loads and validates required environment variables
"""
import os
from typing import Optional
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class ComplianceConfig:
    """Configuration class for compliance agent environment variables"""
    
    def __init__(self):
        # Required API keys
        self.openai_api_key = self._get_required_env("OPENAI_API_KEY")
        
        # Optional API keys
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
        self.langsmith_api_key = os.getenv("LANGSMITH_API_KEY")
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY")
        
        # Model configurations
        self.gpt_mini_model = os.getenv("GPT_MINI_MODEL", "gpt-5-mini-2025-08-07")
        self.gpt_standard_model = os.getenv("GPT_STANDARD_MODEL", "gpt-5-2025-08-07")
        self.perplexity_model = os.getenv("PERPLEXITY_RESEARCH_MODEL", "sonar-deep-research")
        self.openai_temperature = int(os.getenv("OPENAI_TEMPERATURE", "1"))
        
        # LangSmith configuration
        self.langsmith_project = os.getenv("LANGSMITH_PROJECT", "compliance-agent-dev")
        self.langchain_tracing = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
        
        # Development settings
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        # Compliance settings
        self.default_risk_threshold = float(os.getenv("DEFAULT_RISK_THRESHOLD", "0.7"))
        self.supported_frameworks = os.getenv("COMPLIANCE_FRAMEWORKS", "GDPR,SOX,HIPAA,PCI-DSS,SOC2").split(",")
        
        # Configure logging
        self._configure_logging()
        
        # Log configuration status
        self._log_configuration_status()
    
    def _get_required_env(self, var_name: str) -> str:
        """Get required environment variable or raise error"""
        value = os.getenv(var_name)
        if not value:
            raise ValueError(f"Required environment variable {var_name} is not set")
        return value
    
    def _configure_logging(self):
        """Configure logging for LangGraph Platform"""
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()  # Platform handles log aggregation
            ],
            force=True  # Override any existing configuration
        )
    
    def _log_configuration_status(self):
        """Log configuration status for debugging"""
        logger.info(f"Compliance Agent Configuration:")
        logger.info(f"- Environment: {self.environment}")
        logger.info(f"- GPT Mini Model: {self.gpt_mini_model}")
        logger.info(f"- GPT Standard Model: {self.gpt_standard_model}")
        logger.info(f"- OpenAI Temperature: {self.openai_temperature}")
        logger.info(f"- Perplexity Available: {'Yes' if self.perplexity_api_key else 'No'}")
        logger.info(f"- LangSmith Tracing: {'Enabled' if self.langchain_tracing else 'Disabled'}")
        logger.info(f"- Supported Frameworks: {', '.join(self.supported_frameworks)}")

# Global configuration instance
config = ComplianceConfig()
