from fastapi import HTTPException, status


class PermissionDenied(HTTPException):
    def __init__(self, permission: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission: {permission}",
        )
