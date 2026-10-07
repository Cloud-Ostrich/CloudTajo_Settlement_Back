from typing import NoReturn

from fastapi import HTTPException, status


def raise_api_error(
    message: str,
    error_code: str,
    http_status: int = status.HTTP_401_UNAUTHORIZED,
) -> NoReturn:
    raise HTTPException(
        status_code=http_status,
        detail={
            "success": False,
            "message": message,
            "errorCode": error_code,
        },
    )
