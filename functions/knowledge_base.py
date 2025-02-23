from firebase_admin import storage
from google.cloud import storage as google_storage
import os
import requests
from typing import Optional
import functions_framework
from datetime import datetime
import json

class KnowledgeBaseUploader:
    def __init__(self):
        """Initialize the uploader with ElevenLabs API key."""
        self.api_key = os.getenv('ELEVEN_LABS_API_KEY')
        self.base_url = "https://api.elevenlabs.io"
        self.bucket = storage.bucket()
        
    def upload_file(self, file_path: str) -> dict:
        """
        Upload a file to the ElevenLabs knowledge base.
        
        Args:
            file_path: Path to the file to upload
            
        Returns:
            Response JSON from the API
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        endpoint = f"{self.base_url}/v1/convai/knowledge-base"
        
        headers = {
            "xi-api-key": self.api_key
        }
        
        # Open and prepare the file for upload
        with open(file_path, 'rb') as f:
            files = {
                'file': (os.path.basename(file_path), f, 'text/plain')
            }
            
            try:
                response = requests.post(
                    endpoint,
                    headers=headers,
                    files=files
                )
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                print(f"Error uploading file: {e}")
                if response.text:
                    print(f"Response: {response.text}")
                raise

    def upload_file_from_json(self, json_data: dict) -> dict:
        """
        Upload knowledge base data from a JSON object.
        
        Args:
            json_data: Dictionary containing the knowledge base data
            
        Returns:
            Response JSON from the API
        """
        endpoint = f"{self.base_url}/v1/convai/knowledge-base"
        
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=json_data
            )
            response.raise_for_status()
            return response.json()
                
        except requests.exceptions.RequestException as e:
            print(f"Error uploading knowledge base: {e}")
            if response.text:
                print(f"Response: {response.text}")
            raise

    def create_agent_from_knowledge_base(self, knowledge_base_id: str, name: Optional[str] = None) -> dict:
        """
        Create an agent using a knowledge base document ID.
        
        Args:
            knowledge_base_id: ID of the knowledge base document to use
            name: Optional name for the agent
            
        Returns:
            Response JSON from the API containing the created agent details
        """
        endpoint = f"{self.base_url}/v1/convai/agents/create"
        
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Prepare the request payload
        payload = {
            "name": name or f"Agent for KB {knowledge_base_id}",
            "conversation_config": {
                "agent": {
                    "prompt": {
                        "knowledge_base": [{
                            "id": knowledge_base_id,
                            "type": "file",
                            "name": "presentation"
                        }]
                    }
                }
            }
        }
        
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Error creating agent: {e}")
            if hasattr(e, 'response') and e.response.text:
                print(f"Response: {e.response.text}")
            raise

def handle_knowledge_base_upload_from_request(request):
    """Cloud Function entry point for knowledge base upload"""

    request_json = request.get_json()
    script_file_path = request_json['script_file_path']  # Path in Cloud Storage
    handle_knowledge_base_upload(script_file_path, storage_client=storage.bucket("presentable-b5545.firebasestorage.app"))

def handle_knowledge_base_upload_from_bucket_trigger(event):
    """Cloud Function entry point for knowledge base upload"""
    # Get file path from event
    bucket_name = event.bucket
    file_path = event.name
    bucket = storage.bucket(bucket_name)

    handle_knowledge_base_upload(file_path, storage_client=bucket)


def handle_knowledge_base_upload(script_file_path: str, storage_client):
    """Cloud Function entry point for knowledge base upload"""
    try:
        presentation_id = os.path.splitext(os.path.basename(pdf_path))[0]
        
        # Get the script data from Cloud Storage
        blob = storage_client.blob(script_file_path)
        json_data = json.loads(blob.download_as_string())
        
        # Upload to ElevenLabs
        uploader = KnowledgeBaseUploader()
        kb_response = uploader.upload_file_from_json(json_data)
        
        # Create agent if knowledge base upload successful
        if kb_response and 'id' in kb_response:
            agent_response = uploader.create_agent_from_knowledge_base(
                kb_response['id'],
                name=presentation_id
            )
            
            # Store a reference to the original JSON in Cloud Storage
            reference_path = f"knowledge_base/{kb_response['id']}/source.json"
            reference_blob = uploader.bucket.blob(reference_path)
            reference_blob.upload_from_string(
                json.dumps(json_data),
                content_type='application/json'
            )
            
            return {
                'success': True,
                'knowledge_base': kb_response,
                'agent': agent_response,
                'reference_path': reference_path
            }, 200
            
        return {'error': 'Failed to upload knowledge base'}, 500
        
    except Exception as e:
        return {'error': str(e)}, 500
