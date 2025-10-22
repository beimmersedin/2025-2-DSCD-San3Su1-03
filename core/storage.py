# core/storage.py
import os, uuid, pathlib, shutil, boto3
from io import BytesIO
from botocore.config import Config

class Storage:
    def put(self, fileobj, key, content_type): ...
    def url(self, key): ...

class LocalStorage(Storage):
    def __init__(self, root="data/uploads"):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.bucket = "local-bucket"  # 관찰용

    def put(self, fileobj, key, content_type):
        fileobj.seek(0)
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            shutil.copyfileobj(fileobj, f)
        return "local-etag"  # 업로드 성공표시
    
    def url(self, key):
        return str(self.root / key)

class S3Storage(Storage):
    def __init__(self, bucket, region):
        assert bucket, "AWS_S3_BUCKET 비어있음"
        assert region, "AWS_REGION 비어있음"
        self.bucket=bucket
        self.region=region
        self.s3 = boto3.client(
            "s3",
            region_name=region,
            config=Config(s3={"addressing_style": "virtual"})
        )

    def put(self, fileobj, key, content_type):
        fileobj.seek(0)         # ← 업로드 전에 항상 리와인드
        self.s3.upload_fileobj(
            Fileobj=fileobj,
            Bucket=self.bucket,
            Key=key,
            ExtraArgs={"ContentType": content_type, "ACL": "private"}
        )
        # etag 확인(선택)
        head = self.s3.head_object(Bucket=self.bucket, Key=key)
        return head.get("ETag")
    
    def url(self, key, expires=3600):
        return self.s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires
        )

def get_storage():
    backend = os.getenv("STORAGE_BACKEND","local").lower()
    if backend == "s3":
        # 꼭 이 이름들로 환경변수 세팅: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION / AWS_S3_BUCKET
        return S3Storage(os.getenv("AWS_S3_BUCKET"), os.getenv("AWS_REGION"))
    return LocalStorage(os.getenv("LOCAL_UPLOAD_ROOT","data/uploads"))
