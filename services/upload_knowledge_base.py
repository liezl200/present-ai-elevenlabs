import os
import requests
from typing import Optional

class KnowledgeBaseUploader:
    def __init__(self, api_key: str):
        """Initialize the uploader with ElevenLabs API key."""
        self.api_key = api_key
        self.base_url = "https://api.elevenlabs.io"
        
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


def create_agent_from_script(file_path: str, agent_name: str):
    # Get API key from environment variable
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError("Please set ELEVENLABS_API_KEY environment variable")

    # Initialize uploader
    uploader = KnowledgeBaseUploader(api_key)
    
    # Example usage
    try:
        result = uploader.upload_file(file_path)
        print("Upload successful!")
        print(f"Response: {result}")
        uploader.create_agent_from_knowledge_base(result['id'], name=agent_name)
        
    except Exception as e:
        print(f"Failed to upload script: {e}")

def main():
    create_agent_from_script(file_path="script.json", agent_name="Catatonia")
if __name__ == "__main__":
    main()
