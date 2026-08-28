from fastapi import HTTPException, status

class WardNotFoundError(HTTPException):
    def __init__(self, ward_id):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ward with ID '{ward_id}' not found"
        )

class InvalidComparisonError(HTTPException):
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

class EmptyDatasetError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dataset is currently unavailable. Please try again later."
        )

class InvalidInputError(HTTPException):
    def __init__(self, field: str, message: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {field}: {message}"
        )
