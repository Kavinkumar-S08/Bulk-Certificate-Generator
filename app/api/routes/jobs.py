from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.db.session import get_db
from app.models import Certificate, GenerationJob
from app.schemas.job import JobCreateRequest, JobCreateResponse, JobStatusResponse, CertificateListResponse, CertificateResult

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_job(
    request: JobCreateRequest,
    db: Session = Depends(get_db),
):
    job = GenerationJob(
        event_name=request.event_name,
        status="queued",
    )

    try:
        db.add(job)
        db.flush()

        certificates = [
            Certificate(
                job_id=job.id,
                recipient_name=recipient.name,
                recipient_email=str(recipient.email),
                status="pending",
            )
            for recipient in request.recipients
        ]

        db.add_all(certificates)
        db.commit()
        db.refresh(job)

        return JobCreateResponse(
            job_id=job.id,
            status=job.status,
            total_certificates=len(certificates),
        )

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create certificate job",
        ) from exc


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: int,
    db: Session = Depends(get_db),
):
    job = db.get(GenerationJob, job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    counts = db.execute(
        select(
            func.count(Certificate.id).label("total"),
            func.count(Certificate.id)
            .filter(Certificate.status == "success")
            .label("successful"),
            func.count(Certificate.id)
            .filter(Certificate.status == "failed")
            .label("failed"),
            func.count(Certificate.id)
            .filter(
                Certificate.status.in_(["pending", "processing"])
            )
            .label("pending"),
        ).where(Certificate.job_id == job_id)
    ).one()

    total = counts.total
    successful = counts.successful
    failed = counts.failed
    pending = counts.pending

    progress = (
        round((successful + failed) * 100 / total)
        if total
        else 0
    )

    return JobStatusResponse(
        job_id=job.id,
        event_name=job.event_name,
        status=job.status,
        total_certificates=total,
        successful=successful,
        failed=failed,
        pending=pending,
        progress_percent=progress,
    )


@router.get("/{job_id}/certificates", response_model=CertificateListResponse)
def list_certificates(
    job_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    job = db.get(GenerationJob, job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    total = db.scalar(
        select(func.count(Certificate.id)).where(
            Certificate.job_id == job_id
        )
    )

    certificates = db.scalars(
        select(Certificate)
        .where(Certificate.job_id == job_id)
        .order_by(Certificate.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return CertificateListResponse(
        job_id=job_id,
        page=page,
        page_size=page_size,
        total=total or 0,
        certificates=[
            CertificateResult(
                certificate_id=cert.id,
                recipient_name=cert.recipient_name,
                status=cert.status,
                error_message=cert.error_message,
            )
            for cert in certificates
        ],
    )