"""
LLM Utilities for Compliance Agent
Centralized model management and API interactions
"""
import sys
import os
from pathlib import Path

# Add the src directory to Python path
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import httpx
import logging
import json
from config import config

logger = logging.getLogger(__name__)

class LLMManager:
    """Centralized LLM management for compliance agent"""
    
    def __init__(self):
        self.openai_api_key = config.openai_api_key
        self.perplexity_api_key = config.perplexity_api_key
        self.temperature = config.openai_temperature
        
        # Model configurations
        self.gpt_mini_model = config.gpt_mini_model
        self.gpt_standard_model = config.gpt_standard_model
        self.perplexity_model = config.perplexity_model
    
    def get_mini_llm(self) -> ChatOpenAI:
        """Get GPT Mini model for quick classification and lightweight tasks"""
        return ChatOpenAI(
            model=self.gpt_mini_model,
            temperature=self.temperature,
            openai_api_key=self.openai_api_key
        )
    
    def get_standard_llm(self) -> ChatOpenAI:
        """Get GPT Standard model for complex analysis and detailed work"""
        return ChatOpenAI(
            model=self.gpt_standard_model,
            temperature=self.temperature,
            openai_api_key=self.openai_api_key
        )
    
    async def query_perplexity(self, query: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Query Perplexity for latest compliance research and regulatory updates"""
        if not self.perplexity_api_key:
            logger.warning("Perplexity API key not configured")
            return {"choices": [{"message": {"content": "Research API unavailable"}}]}
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": query})
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.perplexity_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.perplexity_model,
                        "messages": messages,
                        "temperature": 0.2,
                        "return_citations": True,
                        "return_images": False
                    },
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Perplexity API error: {response.status_code} - {response.text}")
                    return {"choices": [{"message": {"content": "Research query failed"}}]}
                    
        except httpx.TimeoutException:
            logger.error("Perplexity query timed out")
            return {"choices": [{"message": {"content": "Research query timed out"}}]}
        except Exception as e:
            logger.error(f"Perplexity query failed: {e}")
            return {"choices": [{"message": {"content": "Research unavailable due to error"}}]}
    
    async def safe_llm_query(self, llm: ChatOpenAI, prompt: str, parse_json: bool = False) -> Dict[str, Any]:
        """Safely query LLM with error handling and optional JSON parsing"""
        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()
            
            if parse_json:
                # Try to extract JSON from response
                if content.startswith("```json"):
                    content = content.split("```json")[1].split("```")[0].strip()
                elif content.startswith("```"):
                    content = content.split("```")[1].split("```")[0].strip()
                
                return json.loads(content)
            else:
                return {"content": content, "success": True}
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            return {"error": "Invalid JSON response", "raw_content": content if 'content' in locals() else ""}
        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            return {"error": str(e), "success": False}

# Global instance
llm_manager = LLMManager()
