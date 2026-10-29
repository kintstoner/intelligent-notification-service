from fastapi import APIRouter, HTTPException, Request, status

from api.schemas import CreatedResponse, CreateRequestBody, StatusResponse
from domain.models import NotificationRequest
from infra.repository import RequestRepository

router = APIRouter(prefix="/v1/requests", tags=["requests"])


def _repository(request: Request) -> RequestRepository:
    return request.app.state.repository


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreatedResponse)
def create_request(body: CreateRequestBody, request: Request) -> CreatedResponse:
    notification_request = NotificationRequest(user_input=body.user_input)
    _repository(request).add(notification_request)
    return CreatedResponse(id=notification_request.id)


@router.get("/{request_id}", response_model=StatusResponse, response_model_exclude_none=True)
def get_request(request_id: str, request: Request) -> StatusResponse:
    notification_request = _repository(request).get(request_id)
    if notification_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return StatusResponse(
        id=notification_request.id, status=notification_request.status, reason=notification_request.reason
    )
