from firebase_admin import storage
from datetime import datetime
import json
import os
import traceback

def process_pdf_to_json_script(pdf_path: str) -> dict:
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

def on_pdf_uploaded(event):
    """Background Cloud Function to be triggered by Cloud Storage."""
    try:
        # Get file path from event
        bucket_name = event.bucket
        file_path = event.name
        
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
        json_data = process_pdf_to_json_script(temp_pdf_path)
        
        # Upload JSON to a new location
        presentation_id = os.path.splitext(os.path.basename(file_path))[0]
        json_path = f"presentations/{presentation_id}/content.json"
        json_blob = bucket.blob(json_path)
        
        json_blob.upload_from_string(
            json.dumps(json_data),
            content_type='application/json'
        )
        
        # Clean up temporary file
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
            
        # Update metadata in original PDF blob
        pdf_blob.metadata = {
            'processed': 'true',
            'json_path': json_path,
            'processed_at': datetime.now().isoformat()
        }
        pdf_blob.patch()
        
        return {
            'success': True,
            'message': f'Successfully processed PDF and created presentation {presentation_id}',
            'presentation_id': presentation_id
        }
            
    except Exception as e:
        print(f'Error processing PDF: {str(e)}')
        print('Traceback:')
        print(traceback.format_exc())
        return {
            'success': False,
            'message': f'Error processing PDF: {str(e)}',
            'traceback': traceback.format_exc(),
            'file_path': file_path if 'file_path' in locals() else 'unknown'
        }
