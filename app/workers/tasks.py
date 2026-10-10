from sqlalchemy import func, select, update

from app.db.session import SessionLocal
from app.models import Certificate, GenerationJob
from app.services.certificate_service import generate_single_certificate
from app.workers.celery_app import celery_app


def refresh_job_status(db, job_id: int) -> str:
    counts = db.execute(
        select(Certificate.status, func.count())
        .where(Certificate.job_id == job_id)
        .group_by(Certificate.status)
    ).all()

    status_counts = dict(counts)
    total = sum(status_counts.values())
    successful = status_counts.get("success", 0)
    failed = status_counts.get("failed", 0)

    if successful + failed < total:
        job_status = "processing"
    elif failed:
        job_status = "completed_with_errors"
    else:
        job_status = "completed"

    db.execute(
        update(GenerationJob)
        .where(GenerationJob.id == job_id)
        .values(status=job_status)
    )
    db.commit()

    return job_status


@celery_app.task(
    name="app.workers.tasks.generate_certificate_task",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def generate_certificate_task(self, certificate_id: int):
    db = SessionLocal()
    job_id = None

    try:
        certificate = db.get(Certificate, certificate_id)

        if certificate is None:
            raise ValueError(f"Certificate {certificate_id} not found")

        job_id = certificate.job_id

        # Mark the job as processing without resetting a completed job.
        db.execute(
            update(GenerationJob)
            .where(
                GenerationJob.id == job_id,
                GenerationJob.status == "queued",
            )
            .values(status="processing")
        )
        db.commit()

        certificate = generate_single_certificate(db, certificate_id)
        job_status = refresh_job_status(db, job_id)

        return {
            "certificate_id": certificate.id,
            "status": certificate.status,
            "job_status": job_status,
        }

    except Exception as exc:
        db.rollback()

        if job_id is not None and self.request.retries < self.max_retries:
            # Make a failed certificate eligible for the scheduled retry.
            db.execute(
                update(Certificate)
                .where(
                    Certificate.id == certificate_id,
                    Certificate.status == "failed",
                )
                .values(status="pending")
            )
            db.commit()

            raise self.retry(exc=exc)

        if job_id is not None:
            refresh_job_status(db, job_id)

        raise

    finally:
        db.close()