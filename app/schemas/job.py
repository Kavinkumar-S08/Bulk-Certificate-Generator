from pydantic import BaseModel, EmailStr, Field


class RecipientInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr


class JobCreateRequest(BaseModel):
    event_name: str = Field(min_length=1, max_length=200)
    recipients: list[RecipientInput] = Field(min_length=1, max_length=1000)


class JobCreateResponse(BaseModel):
    job_id: int
    status: str
    total_certificates: int


class JobStatusResponse(BaseModel):
    job_id: int
    event_name: str
    status: str
    total_certificates: int
    successful: int
    failed: int
    pending: int
    progress_percent: int


class CertificateResult(BaseModel):
    certificate_id: int
    recipient_name: str
    status: str
    error_message: str | None


class CertificateListResponse(BaseModel):
    job_id: int
    page: int
    page_size: int
    total: int
    certificates: list[CertificateResult]