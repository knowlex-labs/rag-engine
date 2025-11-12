from fastapi import APIRouter
from typing import Optional
from pydantic import BaseModel
from services.user_service import user_service
from models.api_models import ApiResponse, ApiResponseWithBody

router = APIRouter()


@router.get("/")
def list_users() -> ApiResponseWithBody:
    try:
        user_ids = user_service.list_users()
        return ApiResponseWithBody(
            status="SUCCESS",
            message="Users retrieved successfully",
            body={"users": user_ids}
        )
    except Exception as e:
        return ApiResponseWithBody(
            status="FAILURE",
            message=f"Failed to list users: {str(e)}",
            body={"users": []}
        )


class RegisterUserRequest(BaseModel):
    user_id: str
    email: str
    name: str
    anonymous_session_id: Optional[str] = None


class CreateAnonymousUserResponse(BaseModel):
    status: str
    message: str
    user_id: str


@router.post("/register")
def register_user(request: RegisterUserRequest) -> ApiResponseWithBody:
    result = user_service.register_user(
        user_id=request.user_id,
        email=request.email,
        name=request.name,
        anonymous_session_id=request.anonymous_session_id
    )

    if result["status"] == "SUCCESS":
        return ApiResponseWithBody(
            status="SUCCESS",
            message=result["message"],
            body={"user_id": result["user_id"]}
        )
    else:
        return ApiResponseWithBody(
            status="FAILURE",
            message=result["message"],
            body={}
        )


@router.post("/anonymous")
def create_anonymous_user() -> CreateAnonymousUserResponse:
    try:
        user_id = user_service.create_anonymous_user()
        return CreateAnonymousUserResponse(
            status="SUCCESS",
            message="Anonymous user created",
            user_id=user_id
        )
    except Exception as e:
        return CreateAnonymousUserResponse(
            status="FAILURE",
            message=str(e),
            user_id=""
        )


@router.get("/{user_id}")
def get_user(user_id: str) -> ApiResponseWithBody:
    user = user_service.get_user(user_id)
    if user:
        return ApiResponseWithBody(
            status="SUCCESS",
            message="User found",
            body=user
        )
    else:
        return ApiResponseWithBody(
            status="FAILURE",
            message="User not found",
            body={}
        )


@router.post("/cleanup")
def cleanup_anonymous_users(days_old: int = 30) -> ApiResponse:
    try:
        user_service.cleanup_anonymous_users(days_old)
        return ApiResponse(
            status="SUCCESS",
            message=f"Cleaned up anonymous users older than {days_old} days"
        )
    except Exception as e:
        return ApiResponse(
            status="FAILURE",
            message=str(e)
        )