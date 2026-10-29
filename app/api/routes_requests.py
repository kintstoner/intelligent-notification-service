from fastapi import APIRouter, HTTPException, Request, status

from api.schemas import CreatedResponse, CreateRequestBody, StatusResponse
from domain.models import NotificationRequest, Status
from infra.repository import RequestRepository
from services.pipeline import Pipeline

router = APIRouter(prefix="/v1/requests", tags=["requests"])


def _repository(request: Request) -> RequestRepository:
    return request.app.state.repository


def _pipeline(request: Request) -> Pipeline:
    return request.app.state.pipeline


def _find(request: Request, request_id: str) -> NotificationRequest:
    notification_request = _repository(request).get(request_id)
    if notification_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return notification_request


def _status_of(notification_request: NotificationRequest) -> StatusResponse:
    return StatusResponse(
        id=notification_request.id, status=notification_request.status, reason=notification_request.reason
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreatedResponse)
def create_request(body: CreateRequestBody, request: Request) -> CreatedResponse:
    notification_request = NotificationRequest(user_input=body.user_input)
    _repository(request).add(notification_request)
    return CreatedResponse(id=notification_request.id)


@router.post(
    "/{request_id}/process",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=StatusResponse,
    response_model_exclude_none=True,
)
def process_request(request_id: str, request: Request) -> StatusResponse:
    """
    Accepts the request for processing and returns at once. Idempotent: a request already in the queue, being
    processed or finished is not enqueued again. A full queue is never an error for the caller: the request stays
    queued with a reason and can be processed again later.
    """
    notification_request = _find(request, request_id)
    if notification_request.status == Status.QUEUED and not notification_request.enqueued:
        if _pipeline(request).submit(notification_request):
            notification_request.enqueued = True
            notification_request.reason = None
        else:
            notification_request.reason = "queue_full"
    return _status_of(notification_request)


@router.get("/{request_id}", response_model=StatusResponse, response_model_exclude_none=True)
def get_request(request_id: str, request: Request) -> StatusResponse:
    return _status_of(_find(request, request_id))
