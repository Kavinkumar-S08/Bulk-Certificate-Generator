from pathlib import Path

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Certificate, GenerationJob
from app.services.pdf_generator import generate_certificate_pdf


def generate_single_certificate(
    db: Session,
    certificate_id: int,
) -> Certificate:
    certificate = db.get(Certificate, certificate_id)

    if certificate is None:
        raise ValueError(f"Certificate {certificate_id} not found")

    # Return an existing successful result without generating it again.
    if (
        certificate.status == "success"
        and certificate.file_path
        and Path(certificate.file_path).is_file()
    ):
        return certificate

    # Atomically claim the certificate.
    # Only one worker can change pending/failed to processing.
    claim = db.execute(
        update(Certificate)
        .where(
            Certificate.id == certificate_id,
            Certificate.status.in_(["pending", "failed"]),
        )
        .values(status="processing", error_message=None)
    )

    if claim.rowcount != 1:
        db.rollback()

        current = db.get(Certificate, certificate_id)

        if (
            current
            and current.status == "success"
            and current.file_path
            and Path(current.file_path).is_file()
        ):
            return current

        current_status = current.status if current else "not found"
        raise ValueError(
            f"Certificate {certificate_id} cannot be processed "
            f"because its current status is '{current_status}'"
        )

    db.commit()

    try:
        certificate = db.get(Certificate, certificate_id)
        job = db.get(GenerationJob, certificate.job_id)

        if job is None:
            raise ValueError(f"Job {certificate.job_id} not found")

        file_path = generate_certificate_pdf(
            certificate_id=certificate.id,
            recipient_name=certificate.recipient_name,
            event_name=job.event_name,
        )

        if not Path(file_path).is_file():
            raise RuntimeError("The generated PDF file was not found")

        certificate.file_path = file_path
        certificate.status = "success"
        certificate.error_message = None
        db.commit()

        return certificate

    except Exception as exc:
        db.rollback()

        try:
            db.execute(
                update(Certificate)
                .where(
                    Certificate.id == certificate_id,
                    Certificate.status == "processing",
                )
                .values(
                    status="failed",
                    error_message=str(exc)[:2000],
                )
            )
            db.commit()
        except Exception:
            db.rollback()

        raise