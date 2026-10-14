import os
import boto3
from botocore.config import Config
from config import R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_PUBLIC_URL_PREFIX

def get_s3_client():
    if not R2_ACCOUNT_ID or not R2_ACCESS_KEY_ID:
        return None
    endpoint = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto"
    )

def download_file(file_key_or_url: str, local_path: str) -> str:
    s3 = get_s3_client()
    if s3 and not file_key_or_url.startswith("http"):
        s3.download_file(R2_BUCKET_NAME, file_key_or_url, local_path)
        return local_path
    
    # Direct HTTP download
    import requests
    with requests.get(file_key_or_url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_path

def upload_file(local_path: str, destination_key: str) -> str:
    s3 = get_s3_client()
    if s3:
        s3.upload_file(local_path, R2_BUCKET_NAME, destination_key, ExtraArgs={"ContentType": "video/mp4"})
        if R2_PUBLIC_URL_PREFIX:
            return f"{R2_PUBLIC_URL_PREFIX.rstrip('/')}/{destination_key}"
        return f"https://{R2_BUCKET_NAME}.r2.dev/{destination_key}"
    return local_path
