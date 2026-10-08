import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()


class StorageError(RuntimeError):
    pass


class ObjectStorage:
    def __init__(self) -> None:
        self.bucket = os.getenv("NCP_OBJECT_STORAGE_BUCKET")
        self.endpoint = os.getenv("NCP_OBJECT_STORAGE_ENDPOINT")
        self.region = os.getenv("NCP_OBJECT_STORAGE_REGION", "kr-standard")

    def _client(self):
        if not self.bucket or not self.endpoint:
            raise StorageError("Object Storage 설정이 없습니다.")
        try:
            import boto3
        except ImportError as error:
            raise StorageError("boto3 의존성이 설치되지 않았습니다.") from error
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            region_name=self.region,
            aws_access_key_id=os.getenv("NCP_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("NCP_SECRET_KEY"),
        )

    def put(self, object_key: str, content: bytes, content_type: str) -> None:
        try:
            self._client().put_object(
                Bucket=self.bucket, Key=object_key, Body=content, ContentType=content_type
            )
        except Exception as error:
            raise StorageError("Object Storage 파일 저장에 실패했습니다.") from error

    def delete(self, object_key: str) -> None:
        try:
            self._client().delete_object(Bucket=self.bucket, Key=object_key)
        except Exception as error:
            raise StorageError("Object Storage 파일 삭제에 실패했습니다.") from error

    def get(self, object_key: str) -> bytes:
        try:
            response = self._client().get_object(Bucket=self.bucket, Key=object_key)
            return response["Body"].read()
        except Exception as error:
            raise StorageError("Object Storage 파일 조회에 실패했습니다.") from error

    def presigned_get_url(self, object_key: str, expires: int = 300) -> str:
        try:
            return self._client().generate_presigned_url(
                "get_object", Params={"Bucket": self.bucket, "Key": object_key}, ExpiresIn=expires
            )
        except Exception as error:
            raise StorageError("Object Storage 접근 URL 발급에 실패했습니다.") from error


def receipt_object_key(receipt_id: int, filename: str, now: datetime | None = None) -> str:
    current = now or datetime.utcnow()
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"receipts/{current.year}/{current.month:02d}/{receipt_id}.{extension}"
