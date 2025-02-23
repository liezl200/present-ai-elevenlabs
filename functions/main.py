import os
from dotenv import load_dotenv
from firebase_functions import https_fn, storage_fn
from firebase_admin import initialize_app, storage
import google.cloud.storage

# Load environment variables
load_dotenv()

# Initialize Firebase app
app = initialize_app()

@https_fn.on_request(region="us-east1")
def upload_knowledge_base(req: https_fn.Request) -> https_fn.Response:
    """HTTP Cloud Function to handle knowledge base uploads."""
    from knowledge_base import handle_knowledge_base_upload
    return handle_knowledge_base_upload(req)

@https_fn.on_request(region="us-east1")
def process_tts(req: https_fn.Request) -> https_fn.Response:
    """HTTP Cloud Function to handle TTS processing."""
    from tts_processor import handle_tts_request
    return handle_tts_request(req)

@storage_fn.on_object_finalized(region="us-east1")
def process_uploaded_pdf(event: storage_fn.CloudEvent[storage_fn.StorageObjectData]) -> None:
    """Background Cloud Function triggered by a change to a Cloud Storage bucket."""
    from pdf_processor import on_pdf_uploaded
    
    if event.data.content_type == "application/pdf":
        return on_pdf_uploaded(event.data, event.context)
