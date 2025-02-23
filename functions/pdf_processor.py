from firebase_admin import storage
from datetime import datetime
import json
import os

def process_pdf_to_json(pdf_path: str) -> dict:
    """
    Convert PDF to JSON format. This is a placeholder for the actual LLM-based implementation.
    Will be implemented with proper LLM APIs later.
    """
    # TODO: Implement actual PDF to JSON conversion using LLM APIs
    return {
        "title": "Placeholder",
        "slides": [
            {
                "id": "slide1",
                "content": "Placeholder content"
            }
        ]
    }

def on_pdf_uploaded(event, context):
    """Background Cloud Function to be triggered by Cloud Storage."""
    try:
        file = event
        
        # Get file path from event
        bucket_name = file['bucket']
        file_path = file['name']
        
        # Only process PDFs in the uploads directory
        if not file_path.startswith('uploads/') or not file_path.endswith('.pdf'):
            print(f"Skipping file {file_path} - not a PDF in uploads directory")
            return
            
        # Get bucket and create client
        bucket = storage.bucket(bucket_name)
        
        # Download PDF to temporary storage
        pdf_blob = bucket.blob(file_path)
        temp_pdf_path = f"/tmp/{os.path.basename(file_path)}"
        pdf_blob.download_to_filename(temp_pdf_path)
        
        # Process PDF to JSON
        json_data = process_pdf_to_json(temp_pdf_path)
        
        # Upload JSON to a new location
        presentation_id = os.path.splitext(os.path.basename(file_path))[0]
        json_path = f"presentations/{presentation_id}/content.json"
        json_blob = bucket.blob(json_path)
        
        json_blob.upload_from_string(
            json.dumps(json_data),
            content_type='application/json'
        )
        
        # Clean up temporary file
        os.remove(temp_pdf_path)
        
        # Update metadata in original PDF blob
        pdf_blob.metadata = {
            'processed': 'true',
            'json_path': json_path,
            'processed_at': datetime.now().isoformat()
        }
        pdf_blob.patch()
        
        print(f"Successfully processed {file_path} to {json_path}")
        return json_path
        
    except Exception as e:
        print(f"Error processing PDF {file_path}: {str(e)}")
        raise
