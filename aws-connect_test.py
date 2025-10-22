from dotenv import load_dotenv
load_dotenv()  # .env 파일을 현재 작업 디렉토리에서 읽어옴

import boto3, os

bucket = os.getenv("AWS_S3_BUCKET")
assert bucket, "AWS_S3_BUCKET not set"


session = boto3.Session(
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)
s3 = session.client("s3")

resp = s3.list_objects_v2(Bucket=bucket)
print("✅ ok,", len(resp.get("Contents", [])), "objects")
