from firebase_admin import storage
from typing import List, Optional, Tuple
import asyncio
from datetime import datetime
import json
import os
import traceback
import PyPDF2
from anthropic import AsyncAnthropic
import argparse
import aiohttp
from pydub import AudioSegment
import io
from dotenv import load_dotenv

load_dotenv()

async def generate_narrative_batch(
    pdf_text: list[str],  # List of text content from 3 slides
    start_slide_num: int,
    claude_client,  # Anthropic API client
    storage_client,
    presentation_id: str
) -> bool:
    """
    Generates narrative content for a batch of 3 slides and saves to storage.
    Returns True if successful, False if needs retry.
    """
    SYSTEM_PROMPT = """
    You are a distinguished professor teaching medicine to residents at Harvard. You are known for your friendly tone and uncanny ability to make complex concepts entertaining and memorable while teaching. You have wonderful reviews from all of your students for your precise yet engaging teaching style.

    Your task is to generate a presentation script from lecture slides. Process exactly 3 slides at a time, following this exact format for each slide:

    Slide <slide_number> (<slide_title>): "<slide_script>"

    Example format:
    Slide 1 (Title Slide): "Welcome everyone! Today we're going to dive into a fascinating and important topic - catatonia. As a clinician, you'll find this information invaluable in your practice. Let me guide you through understanding this complex condition."

    Important formatting rules:
    1. Always maintain the exact structure: "Slide X (Title): "Script""
    2. Use straight quotes (") not curly quotes
    3. Keep paragraph breaks within the script using \n
    4. Never break the slide format with additional text between slides
    5. Never ask if you should continue - just process exactly 3 slides and stop
    6. Maintain your engaging professorial tone while following these strict formatting requirements

    Remember to bring your friendly, engaging teaching style to each slide while maintaining this exact formatting structure.
    """

    try:
        # Prepare metadata
        batch_id = f"batch_{start_slide_num}_slides_{start_slide_num}-{start_slide_num+2}"
        metadata = {
            "batch_metadata": {
                "batch_id": batch_id,
                "slide_range": {
                    "start": start_slide_num,
                    "end": start_slide_num + 2
                },
                "status": {
                    "narrative": {
                        "state": "in_progress",
                        "attempts": 0,
                        "last_updated": datetime.utcnow().isoformat()
                    },
                    "json": {
                        "state": "pending",
                        "validation": "pending",
                        "attempts": 0,
                        "last_updated": None
                    }
                }
            }
        }

        # Call Claude with system prompt and slide content
        narrative_response = await claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"Generate scripts for these 3 slides:\n\n{pdf_text}"
            }],
            system=SYSTEM_PROMPT
        )

        # Save narrative to storage
        storage_path = f"presentations/{presentation_id}/intermediate_outputs/narrative/{batch_id}.txt"
        target_blob = storage_client.blob(storage_path)
        print(narrative_response.content[0].text)
        target_blob.upload_from_string(narrative_response.content[0].text)
        print(f"uploaded to {storage_path}")
        # Update metadata
        metadata["batch_metadata"]["status"]["narrative"].update({
            "state": "completed",
            "last_updated": datetime.utcnow().isoformat()
        })
        metadata_path = f"{storage_path}.metadata.json"
        metadata_blob = storage_client.blob(metadata_path)
        metadata_blob.upload_from_string(json.dumps(metadata))

        return True

    except Exception as e:
        print(traceback.format_exc())
        # Update metadata with failure
        metadata["batch_metadata"]["status"]["narrative"].update({
            "state": "failed",
            "attempts": metadata["batch_metadata"]["status"]["narrative"]["attempts"] + 1,
            "last_updated": datetime.utcnow().isoformat(),
            "error": str(e)
        })
        metadata_path = f"{storage_path}.metadata.json"
        metadata_blob = storage_client.blob(metadata_path)
        metadata_blob.upload_from_string(json.dumps(metadata))
        return False

async def convert_to_json_batch(
    narrative_text: str,
    batch_id: str,
    claude_client,
    storage_client,
    presentation_id: str
) -> bool:
    """
    Converts narrative batch to JSON format and validates the output.
    Returns True if successful, False if needs retry.
    """
    # Extract start slide number from batch_id
    start_slide_num = int(batch_id.split("_")[1])
    
    JSON_CONVERSION_PROMPT = """
    Your task is to convert the following slide scripts into a strictly formatted JSON array. You must follow these validation rules exactly.

    Required format:
    {
        "slides": [
            {
                "slide": <number>,
                "title": "<exact title from slides>",
                "script": "<complete script text>"
            },
            ...
        ]
    }

    Validation rules:
    1. Titles must be preserved exactly as given, without adding or removing punctuation
    2. Scripts must:
       - Preserve all line breaks as \\n
       - Maintain all original punctuation
       - Keep all formatting like bullet points and lists
       - Not contain unescaped quotes
    3. No empty or null values are allowed in any field
    4. No additional fields beyond slide, title, and script
    5. Arrays must be properly terminated
    6. The outer object must contain only the "slides" key

    Return only valid JSON with no additional text or commentary.
    """
    try:
        # Initialize metadata
        metadata = {
            "batch_metadata": {
                "batch_id": batch_id,
                "status": {
                    "json": {
                        "state": "in_progress",
                        "validation": "pending",
                        "attempts": 0,
                        "last_updated": datetime.utcnow().isoformat()
                    }
                }
            }
        }
        
        metadata_path = f"presentations/{presentation_id}/intermediate_outputs/narrative/{batch_id}.txt.metadata.json"
        
        # Try to load existing metadata if it exists
        try:
            metadata_blob = storage_client.blob(metadata_path)
            existing_metadata = json.loads(metadata_blob.download_as_string().decode('utf-8'))
            metadata["batch_metadata"]["status"]["json"]["attempts"] = existing_metadata["batch_metadata"]["status"]["json"]["attempts"]
        except Exception:
            # If metadata doesn't exist or can't be loaded, use the default initialized above
            pass

        # Call Claude for JSON conversion
        json_response = await claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"Convert this to JSON:\n\n{narrative_text}"
            }],
            system=JSON_CONVERSION_PROMPT
        )

        # Validate JSON structure
        try:
            json_data = json.loads(json_response.content[0].text)
            
            # Basic validation
            assert "slides" in json_data, "Missing 'slides' key"
            assert isinstance(json_data["slides"], list), "'slides' must be an array"
            
            for slide in json_data["slides"]:
                assert all(k in slide for k in ["slide", "title", "script"]), "Missing required fields"
                assert isinstance(slide["slide"], int), "Slide number must be integer"
                assert isinstance(slide["title"], str) and slide["title"], "Invalid title"
                assert isinstance(slide["script"], str) and slide["script"], "Invalid script"

            # Save validated JSON
            json_path = f"presentations/{presentation_id}/intermediate_outputs/json/{batch_id}.json"
            json_blob = storage_client.blob(json_path)
            json_blob.upload_from_string(json.dumps(json_data, ensure_ascii=False, indent=2))

            # Update metadata
            metadata["batch_metadata"]["status"]["json"].update({
                "state": "completed",
                "validation": "passed",
                "last_updated": datetime.utcnow().isoformat()
            })
            metadata_blob = storage_client.blob(metadata_path)
            metadata_blob.upload_from_string(json.dumps(metadata))

            return True

        except (json.JSONDecodeError, AssertionError) as e:
            raise ValueError(f"JSON validation failed: {str(e)}")

    except Exception as e:
        # Update metadata with failure
        metadata["batch_metadata"]["status"]["json"].update({
            "state": "failed",
            "validation": "failed",
            "attempts": metadata["batch_metadata"]["status"]["json"]["attempts"] + 1,
            "last_updated": datetime.utcnow().isoformat(),
            "error": str(e)
        })
        metadata_blob = storage_client.blob(metadata_path)
        metadata_blob.upload_from_string(json.dumps(metadata))
        return False

async def process_presentation(
    presentation_id: str,
    pdf_slides: List[str],  # List of text content from all slides
    claude_client,
    storage_client
) -> Optional[str]:
    """
    Main orchestration function for processing slides and generating the final script.
    Returns the path to the final script.json if successful, None if failed.
    """
    
    async def process_batch(start_idx: int, batch_slides: List[str]) -> bool:
        batch_id = f"batch_{start_idx+1}_slides_{start_idx+1}-{start_idx+3}"
        
        # Step 1: Generate narrative with retries
        narrative_success = False
        for attempt in range(2):  # Try narrative generation twice
            narrative_success = await generate_narrative_batch(
                pdf_text=batch_slides,
                start_slide_num=start_idx + 1,
                claude_client=claude_client,
                storage_client=storage_client,
                presentation_id=presentation_id
            )
            if narrative_success:
                break
        
        if not narrative_success:
            print(f"Failed to generate narrative for batch {batch_id} after 2 attempts")
            return False

        # Get narrative text for JSON conversion
        narrative_path = f"presentations/{presentation_id}/intermediate_outputs/narrative/{batch_id}.txt"
        blob = storage_client.blob(narrative_path)
        narrative_text = blob.download_as_string().decode('utf-8')

        # Step 2: Convert to JSON with retries
        json_success = False
        for attempt in range(2):  # Try JSON conversion twice
            json_success = await convert_to_json_batch(
                narrative_text=narrative_text,
                batch_id=batch_id,
                claude_client=claude_client,
                storage_client=storage_client,
                presentation_id=presentation_id
            )
            if json_success:
                break

        if not json_success:
            # Try regenerating both narrative and JSON
            for attempt in range(2):
                narrative_success = await generate_narrative_batch(
                    pdf_text=batch_slides,
                    start_slide_num=start_idx + 1,
                    claude_client=claude_client,
                    storage_client=storage_client,
                    presentation_id=presentation_id
                )
                if narrative_success:
                    narrative_text = blob.download_as_string().decode('utf-8')
                    json_success = await convert_to_json_batch(
                        narrative_text=narrative_text,
                        batch_id=batch_id,
                        claude_client=claude_client,
                        storage_client=storage_client,
                        presentation_id=presentation_id
                    )
                    if json_success:
                        break

        if not json_success:
            print(f"Failed to process batch {batch_id} after all retry attempts")
            return False

        return True

    # Create directory structure
    base_path = f"presentations/{presentation_id}"
    intermediate_path = f"{base_path}/intermediate_outputs"
    narrative_path = f"{intermediate_path}/narrative"
    json_path = f"{intermediate_path}/json"
    
    # Process batches of 3 slides with some parallelization
    batch_results = []
    for i in range(0, len(pdf_slides), 3):
        batch_slides = pdf_slides[i:i+3]
        # Allow up to 5 batches to process concurrently
        if len(batch_results) >= 5:
            # Wait for the earliest batch to complete before starting new one
            await batch_results.pop(0)
        
        batch_results.append(asyncio.create_task(process_batch(i, batch_slides)))

    # Wait for remaining batches
    remaining_results = await asyncio.gather(*batch_results)
    if not all(remaining_results):
        return None

    # Combine all JSON batches into final script
    final_slides = []
    for i in range(0, len(pdf_slides), 3):
        batch_id = f"batch_{i+1}_slides_{i+1}-{i+3}"
        json_batch_path = f"presentations/{presentation_id}/intermediate_outputs/json/{batch_id}.json"
        blob = storage_client.blob(json_batch_path)
        batch_json = json.loads(blob.download_as_bytes())
        final_slides.extend(batch_json["slides"])

    final_script = {
        "slides": final_slides
    }

    # Save final script
    final_path = f"{base_path}/script.json"
    final_blob = storage_client.blob(final_path)
    final_blob.upload_from_string(json.dumps(final_script, ensure_ascii=False, indent=2))

    return final_path

async def process_local_pdf(pdf_path: str) -> Optional[str]:
    """
    Process a local PDF file without using Cloud Storage.
    Returns the path to the generated script.json file if successful.
    """
    try:
        # Extract presentation ID from filename
        presentation_id = os.path.splitext(os.path.basename(pdf_path))[0]
        pdf_slides = []
        
        # Extract text from PDF
        with open(pdf_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Extract text from each page/slide
            for page in pdf_reader.pages:
                slide_text = page.extract_text()
                if slide_text.strip():  # Only add non-empty slides
                    pdf_slides.append(slide_text)
        
        # Initialize Claude client
        claude_client = AsyncAnthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
        bucket_name = "presentable-b5545.firebasestorage.app"
        # Create a simple storage client for local files
        bucket = storage.bucket(bucket_name)
        
        # Copy PDF to presentations folder
        # presentation_path = f"presentations/{presentation_id}/input.pdf"
        # await bucket.copy_blob(
        #     source_blob=f"uploads/{presentation_id}.pdf",
        #     destination_blob=presentation_path
        # )
        
        # Process the presentation
        # final_path = await process_presentation(
        #     presentation_id=presentation_id,
        #     pdf_slides=pdf_slides,
        #     claude_client=claude_client,
        #     storage_client=bucket
        # )

        audio_path = await process_audio(
            presentation_id=presentation_id,
            storage_client=bucket
        )
        
        if final_path:
            print(f"Successfully processed PDF. Output saved to: gs://presentable-b5545.firebasestorage.app/{final_path}")
        else:
            print("Failed to process PDF")
        
        return final_path
    
    except Exception as e:
        print(f"Error processing local PDF: {str(e)}")
        traceback.print_exc()
        return None

async def process_audio(presentation_id: str, storage_client) -> Optional[str]:
    """
    Process audio for all slides in parallel using ElevenLabs API.
    Loads the script.json from Cloud Storage and generates audio files.
    Returns the path to the directory containing generated audio files.
    """
    try:
        # Load environment variables
        xi_api_key = os.getenv("YOUR_XI_API_KEY")
        if not xi_api_key:
            raise ValueError("ElevenLabs API key not found in environment variables")

        # Load the script data from Cloud Storage
        base_path = f"presentations/{presentation_id}"
        script_path = f"{base_path}/script.json"
        script_blob = storage_client.blob(script_path)
        
        if not script_blob.exists():
            raise ValueError(f"Script not found at {script_path}")
            
        script_content = script_blob.download_as_text()
        script_data = json.loads(script_content)

        # Extract scripts from slides, excluding any with should_skip=true
        paragraphs = [
            slide['script'] 
            for slide in script_data['slides'] 
            if not slide.get('should_skip', False)
        ]

        voice_id = "JBFqnCBsd6RMkjVDRZzb"  # Default voice ID
        audio_base_path = f"{base_path}/audio"

        async def process_paragraph(
            session: aiohttp.ClientSession, 
            paragraph: str, 
            index: int, 
            total: int
        ) -> Tuple[int, bytes]:
            """Process a single paragraph and return its index and audio content."""
            is_last_paragraph = index == total - 1
            is_first_paragraph = index == 0
            
            async with session.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
                json={
                    "text": paragraph,
                    "model_id": "eleven_multilingual_v2",
                    "previous_text": None if is_first_paragraph else " ".join(paragraphs[:index]),
                    "next_text": None if is_last_paragraph else " ".join(paragraphs[index + 1:])
                },
                headers={"xi-api-key": xi_api_key}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"Error encountered, status: {response.status}, content: {error_text}")
                    raise Exception(f"Failed to process paragraph {index + 1}")
                    
                print(f"Successfully converted paragraph {index + 1}/{total}")
                content = await response.read()
                return index, content

        async def main_audio_processing():
            async with aiohttp.ClientSession() as session:
                # Create tasks for all paragraphs
                tasks = [
                    process_paragraph(session, paragraph, i, len(paragraphs))
                    for i, paragraph in enumerate(paragraphs)
                ]
                
                # Process up to 5 paragraphs concurrently
                segment_results = []
                for batch in range(0, len(tasks), 5):
                    batch_tasks = tasks[batch:batch + 5]
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    segment_results.extend(batch_results)
                
                # Check for any errors
                for result in segment_results:
                    if isinstance(result, Exception):
                        print(f"Error processing paragraph: {result}")
                        return None

                # Sort segments by index and process audio
                sorted_results = sorted(segment_results, key=lambda x: x[0])
                
                # Convert to audio segments and combine
                segments = []
                for i, content in sorted_results:
                    segment = AudioSegment.from_mp3(io.BytesIO(content))
                    segments.append(segment)
                    
                    # Save individual segment to storage
                    segment_path = f"{audio_base_path}/segment_{i}.wav"
                    segment_blob = storage_client.blob(segment_path)
                    
                    # Export to bytes
                    audio_data = io.BytesIO()
                    segment.export(audio_data, format="wav")
                    audio_data.seek(0)
                    segment_blob.upload_from_file(audio_data, content_type="audio/wav")
                
                # Combine all segments
                final_segment = segments[0]
                for segment in segments[1:]:
                    final_segment = final_segment + segment
                
                # Save combined audio to storage
                final_path = f"{audio_base_path}/combined_audio.wav"
                final_blob = storage_client.blob(final_path)
                
                # Export to bytes
                final_audio_data = io.BytesIO()
                final_segment.export(final_audio_data, format="wav")
                final_audio_data.seek(0)
                final_blob.upload_from_file(final_audio_data, content_type="audio/wav")
                
                print(f"Successfully generated audio files in {audio_base_path}")
                return audio_base_path

        return await main_audio_processing()

    except Exception as e:
        print(f"Error in process_audio: {str(e)}")
        print(traceback.format_exc())
        return None

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
        
        # Get bucket and blob
        bucket = storage.bucket(bucket_name)
        pdf_blob = bucket.blob(file_path)
        
        # Download PDF to temp file
        temp_pdf_path = f"/tmp/{os.path.basename(file_path)}"
        pdf_blob.download_to_filename(temp_pdf_path)
        
        # Process PDF to JSON
        presentation_id = os.path.splitext(os.path.basename(file_path))[0]
        pdf_slides = []  # List of text content from all slides
        
        # Extract text from PDF
        with open(temp_pdf_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Extract text from each page/slide
            for page in pdf_reader.pages:
                slide_text = page.extract_text()
                if slide_text.strip():  # Only add non-empty slides
                    pdf_slides.append(slide_text)
        
        # Initialize clients
        claude_client = AsyncAnthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
        storage_client = bucket  # Use the bucket as storage client
        
        # Call process_presentation function
        final_path = asyncio.run(process_presentation(
            presentation_id=presentation_id,
            pdf_slides=pdf_slides,
            claude_client=claude_client,
            storage_client=storage_client
        ))

        if final_path is None:
            print(f"Failed to process presentation json {presentation_id}")
            return
        # call proccess audio function
        audio_path = asyncio.run(process_audio(
            presentation_id=presentation_id,
            storage_client=storage_client
        ))
        
        if audio_path is None:
            print(f"Failed to process presentation audio {presentation_id}")
            return
        
        # # Upload JSON to a new location
        # json_blob = bucket.blob(final_path)
        
        # json_blob.upload_from_string(
        #     json.dumps({"slides": []}),  # Replace with actual JSON data
        #     content_type='application/json'
        # )
        
        # Clean up temp file
        os.remove(temp_pdf_path)
        
        # Update metadata in original PDF blob
        pdf_blob.metadata = {
            'processed': 'true',
            'json_path': final_path,
            'audio_path': audio_path,
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
        traceback.print_exc()
        raise

def main():
    
    from dotenv import load_dotenv
    from firebase_admin import initialize_app, storage
    
    # Initialize Firebase app
    app = initialize_app()

    load_dotenv()
    PDF_PATH = '../notebooks/test.pdf'
    
    if not os.path.exists(PDF_PATH):
        print(f"Error: File not found: {PDF_PATH}")
        return
    
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        return
    
    asyncio.run(process_local_pdf(PDF_PATH))

if __name__ == '__main__':
    main()
