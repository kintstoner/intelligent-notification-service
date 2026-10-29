from pydantic import BaseModel, Field

from domain.models import Status


class CreateRequestBody(BaseModel):
    user_input: str = Field(min_length=1, pattern=r"\S", examples=["Manda un mail a feda@test.com diciendo hola"])


class CreatedResponse(BaseModel):
    id: str


class StatusResponse(BaseModel):
    id: str
    status: Status
    # Extra field, outside the contract: present only when there is something to explain
    reason: str | None = None
