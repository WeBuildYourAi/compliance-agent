"""
Azure Storage and Cosmos DB utilities for Compliance Agent
Handles persistence of compliance documents and assessments
"""
import sys
import os
from pathlib import Path

# Add the src directory to Python path
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from typing import Dict, Any, Optional, List
import logging
import json
import uuid
from datetime import datetime, timedelta
from config import config

# Try to import Azure dependencies - optional for local development
try:
    from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
    from azure.cosmos import CosmosClient, PartitionKey, exceptions
    AZURE_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Azure SDK not installed. Storage features will be disabled.")
    AZURE_AVAILABLE = False
    # Define placeholder exceptions class
    class exceptions:
        class CosmosResourceNotFoundError(Exception):
            pass

logger = logging.getLogger(__name__)

class ComplianceStorageManager:
    """Manages Azure Blob Storage for compliance documents"""
    
    def __init__(self):
        self.connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.container_name = os.getenv("AZURE_BLOB_CONTAINER_COMPLIANCE", "compliance-documents")
        
        if not AZURE_AVAILABLE:
            logger.info("Azure Storage SDK not available - running in local development mode")
            self.blob_service_client = None
        elif self.connection_string:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
                self._initialize_container()
            except Exception as e:
                logger.error(f"Failed to initialize Blob Storage: {e}")
                self.blob_service_client = None
        else:
            logger.info("Azure Storage connection string not configured - storage features disabled")
            self.blob_service_client = None
    
    def _initialize_container(self):
        """Ensure container exists"""
        if not self.blob_service_client:
            return
            
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            if not container_client.exists():
                container_client.create_container()
                logger.info(f"Created container: {self.container_name}")
        except Exception as e:
            logger.error(f"Error initializing container {self.container_name}: {e}")
    
    async def upload_document(
        self,
        document_content: str,
        document_type: str,
        document_id: str,
        metadata: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Upload compliance document to blob storage"""
        if not self.blob_service_client:
            return {"success": False, "error": "Blob storage not configured"}
            
        try:
            # Generate blob name
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            blob_name = f"{document_type}/{document_id}_{timestamp}.json"
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Prepare metadata
            blob_metadata = metadata or {}
            blob_metadata['upload_timestamp'] = datetime.utcnow().isoformat()
            blob_metadata['document_type'] = document_type
            blob_metadata['document_id'] = document_id
            
            # Upload document
            blob_client.upload_blob(
                document_content,
                overwrite=True,
                metadata=blob_metadata
            )
            
            return {
                "success": True,
                "blob_name": blob_name,
                "url": blob_client.url,
                "container": self.container_name,
                "metadata": blob_metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to upload document: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def download_document(
        self,
        blob_name: str
    ) -> Optional[str]:
        """Download document from blob storage"""
        if not self.blob_service_client:
            return None
            
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            download_stream = blob_client.download_blob()
            content = download_stream.readall().decode('utf-8')
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to download document: {e}")
            return None

class ComplianceCosmosManager:
    """Manages Cosmos DB for compliance metadata and tracking"""
    
    def __init__(self):
        self.endpoint = os.getenv("COSMOS_ENDPOINT")
        self.key = os.getenv("COSMOS_KEY")
        self.database_name = os.getenv("COSMOS_DATABASE_NAME")
        self.container_name = os.getenv("COSMOS_CONTAINER_NAME")
        
        if not AZURE_AVAILABLE:
            logger.info("Azure Cosmos SDK not available - running in local development mode")
            self.client = None
            self.container = None
        elif self.endpoint and self.key:
            try:
                self.client = CosmosClient(self.endpoint, self.key)
                self._initialize_database()
            except Exception as e:
                logger.error(f"Failed to initialize Cosmos DB: {e}")
                self.client = None
                self.container = None
        else:
            logger.info("Cosmos DB credentials not configured - metadata storage disabled")
            self.client = None
            self.container = None
    
    def _initialize_database(self):
        """Initialize database and container"""
        try:
            # Create or get database
            self.database = self.client.create_database_if_not_exists(
                id=self.database_name
            )
            
            # Create or get container (serverless - no throughput)
            self.container = self.database.create_container_if_not_exists(
                id=self.container_name,
                partition_key=PartitionKey(path="/document_type")
            )
            
            logger.info(f"Initialized Cosmos DB: {self.database_name}/{self.container_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Cosmos DB: {e}")
            self.container = None
    
    async def save_compliance_record(
        self,
        document_id: str,
        document_type: str,
        assessment_results: Dict[str, Any],
        document_content: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Save compliance assessment record to Cosmos DB"""
        if not self.container:
            return {"success": False, "error": "Cosmos DB not configured"}
            
        try:
            record = {
                "id": document_id,
                "document_type": document_type,
                "assessment_summary": {
                    "compliance_category": assessment_results.get("compliance_category"),
                    "frameworks": assessment_results.get("identified_frameworks", []),
                    "risk_level": assessment_results.get("risk_analysis", {}).get("overall_risk_level"),
                    "compliance_score": assessment_results.get("compliance_score"),
                    "gaps_count": len(assessment_results.get("compliance_gaps", []))
                },
                "document_metadata": {
                    "title": document_content.get("title"),
                    "sections_count": len(document_content.get("sections", [])),
                    "recommendations_count": len(assessment_results.get("control_recommendations", []))
                },
                "risk_analysis": assessment_results.get("risk_analysis", {}),
                "compliance_gaps": assessment_results.get("compliance_gaps", [])[:10],  # Top 10 gaps
                "metadata": {
                    **(metadata or {}),
                    "created_at": datetime.utcnow().isoformat(),
                    "request_id": metadata.get("request_id") if metadata else None,
                    "user_id": metadata.get("user_id") if metadata else None
                },
                "storage_reference": metadata.get("blob_url") if metadata else None,
                "timestamps": {
                    "created": datetime.utcnow().isoformat(),
                    "expires": (datetime.utcnow() + timedelta(days=90)).isoformat()
                }
            }
            
            # Create item in Cosmos DB
            created_item = self.container.create_item(body=record)
            
            logger.info(f"Saved compliance record: {document_id}")
            
            return {
                "success": True,
                "record_id": created_item["id"],
                "document_type": document_type
            }
            
        except Exception as e:
            logger.error(f"Failed to save compliance record: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_compliance_record(
        self,
        document_id: str,
        document_type: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve compliance record from Cosmos DB"""
        if not self.container:
            return None
            
        try:
            item = self.container.read_item(
                item=document_id,
                partition_key=document_type
            )
            return item
        except exceptions.CosmosResourceNotFoundError:
            logger.warning(f"Compliance record not found: {document_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve compliance record: {e}")
            return None
    
    async def query_user_assessments(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Query all compliance assessments for a user"""
        if not self.container:
            return []
            
        try:
            query = "SELECT * FROM c WHERE c.metadata.user_id = @user_id ORDER BY c.timestamps.created DESC"
            parameters = [{"name": "@user_id", "value": user_id}]
            
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                max_item_count=limit
            ))
            
            return items
            
        except Exception as e:
            logger.error(f"Failed to query user assessments: {e}")
            return []

# Global instances
storage_manager = ComplianceStorageManager()
cosmos_manager = ComplianceCosmosManager()
