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
        # print(event)
        # CloudEvent(specversion='1.0', id='14041718879134196', source='//storage.googleapis.com/projects/_/buckets/presentable-b5545.firebasestorage.app', type='google.cloud.storage.object.v1.finalized', time=datetime.datetime(2025, 2, 23, 1, 32, 19, 238223, tzinfo=datetime.timezone.utc), data=StorageObjectData(bucket='presentable-b5545.firebasestorage.app', cache_control=None, component_count=None, content_disposition="inline; filename*=utf-8''bf03f244-037e-477a-ad9a-d82871244c6d.pdf", content_encoding=None, content_language=None, content_type='application/pdf', crc32c='uK+RTg==', customer_encryption=None, etag='CNCItY7T2IsDEAE=', generation='1740274339234896', id='presentable-b5545.firebasestorage.app/uploads/bf03f244-037e-477a-ad9a-d82871244c6d.pdf/1740274339234896', kind='storage#object', md5_hash='IXp8s5TkxnKb0pMbdC5cBA==', media_link='https://storage.googleapis.com/download/storage/v1/b/presentable-b5545.firebasestorage.app/o/uploads%2Fbf03f244-037e-477a-ad9a-d82871244c6d.pdf?generation=1740274339234896&alt=media', metadata={'firebaseStorageDownloadTokens': '6c670138-98b7-4d88-8bcb-2471f8a481c3'}, metageneration='1', name='uploads/bf03f244-037e-477a-ad9a-d82871244c6d.pdf', self_link='https://www.googleapis.com/storage/v1/b/presentable-b5545.firebasestorage.app/o/uploads%2Fbf03f244-037e-477a-ad9a-d82871244c6d.pdf', size='5101113', storage_class='REGIONAL', time_created='2025-02-23T01:32:19.238Z', time_deleted=None, time_storage_class_updated='2025-02-23T01:32:19.238Z', updated='2025-02-23T01:32:19.238Z'), subject='objects/uploads/bf03f244-037e-477a-ad9a-d82871244c6d.pdf')
        return on_pdf_uploaded(event.data)
