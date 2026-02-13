from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = Field(..., description="Request success")
    message: Optional[str] = Field(None, description="Response message")
    data: Optional[T] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginationMeta(BaseModel):
    total: int = Field(..., description="Total records")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Page size")
    total_pages: int = Field(..., description="Total pages")
    has_next: bool = Field(..., description="Has next page")
    has_prev: bool = Field(..., description="Has previous page")


class PaginatedResponse(BaseModel, Generic[T]):
    success: bool = Field(..., description="Request success")
    data: List[T] = Field(..., description="Data list")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    success: bool = Field(False, description="Request success")
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[dict] = Field(None, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SuccessResponse(ApiResponse[None]):
    pass


class DataResponse(ApiResponse[Any]):
    pass


class ListResponse(ApiResponse[List[Any]]):
    pass


class ResponseBuilder:
    @staticmethod
    def success(data: Optional[Any] = None, message: Optional[str] = None) -> ApiResponse[Any]:
        return ApiResponse(success=True, message=message, data=data)

    @staticmethod
    def error(error: str, message: str, details: Optional[dict] = None) -> ErrorResponse:
        return ErrorResponse(error=error, message=message, details=details)

    @staticmethod
    def paginated(data: List[Any], total: int, page: int, page_size: int) -> PaginatedResponse[Any]:
        total_pages = (total + page_size - 1) // page_size
        return PaginatedResponse(
            success=True,
            data=data,
            pagination=PaginationMeta(
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_prev=page > 1,
            ),
        )


class WSMessage(BaseModel):
    type: str = Field(..., description="Message type")
    data: Any = Field(None, description="Message payload")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WSErrorMessage(WSMessage):
    type: str = "error"
    error: str = Field(..., description="Error message")


class WSNotificationMessage(WSMessage):
    type: str = "notification"
    notification_type: str = Field(..., description="Notification type")
    message: str = Field(..., description="Notification message")


class WSSpeechMessage(WSMessage):
    type: str = "speech"
    phase: str = Field(..., description="Current phase")
    agent_id: int = Field(..., description="Speaker agent id")
    content: str = Field(..., description="Speech content")


class WSStatusMessage(WSMessage):
    type: str = "status"
    debate_id: int = Field(..., description="Debate id")
    status: str = Field(..., description="Debate status")
    current_phase: Optional[str] = Field(None, description="Current phase")
    current_step: Optional[int] = Field(None, description="Current step")


class WSScoreMessage(WSMessage):
    type: str = "score"
    debate_id: int = Field(..., description="Debate id")
    pro_score: int = Field(..., description="Pro score")
    con_score: int = Field(..., description="Con score")
    comments: Optional[str] = Field(None, description="Judge comments")
