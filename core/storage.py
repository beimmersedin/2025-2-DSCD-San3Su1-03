# storage.py
import os, uuid, pathlib, shutil, boto3
from io import BytesIO

class Storage:
    def put(self, fileobj, key, content_type): ...
    def url(self, key): ...

class LocalStorage(Storage):
    def __init__(self, root="data/uploads"):
        self.root = pathlib.Path(root); self.root.mkdir(parents=True, exist_ok=True)
    def put(self, fileobj, key, content_type):
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f: shutil.copyfileobj(fileobj, f)
    def url(self, key): return str(self.root / key)

class S3Storage(Storage):
    def __init__(self, bucket, region):
        self.bucket=bucket
        self.s3 = boto3.client("s3", region_name=region)
    def put(self, fileobj, key, content_type):
        self.s3.upload_fileobj(
            Fileobj=fileobj, Bucket=self.bucket, Key=key,
            ExtraArgs={"ContentType": content_type, "ACL": "private"}
        )
    def url(self, key, expires=3600):
        return self.s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires
        )

def get_storage():
    if os.getenv("STORAGE_BACKEND","local") == "s3":
        return S3Storage(os.getenv("AWS_S3_BUCKET"), os.getenv("AWS_REGION"))
    return LocalStorage(os.getenv("LOCAL_UPLOAD_ROOT","data/uploads"))
