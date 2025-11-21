from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.deployment import DeploymentJob, JobStatus
from app.schemas.deployment import (
    DeploymentJobResponse,
    DeploymentJobListResponse,
    DeploymentJobDetailResponse,
    ApiCallLogResponse,
)

router = APIRouter()


@router.get("", response_model=DeploymentJobListResponse)
async def list_jobs(
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[JobStatus] = None,
    peer_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all deployment jobs."""
    query = select(DeploymentJob)

    if status_filter:
        query = query.where(DeploymentJob.status == status_filter)
    if peer_id:
        query = query.where(DeploymentJob.peer_id == peer_id)

    query = query.order_by(DeploymentJob.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    jobs = result.scalars().all()

    # Get total count
    count_query = select(func.count(DeploymentJob.id))
    if status_filter:
        count_query = count_query.where(DeploymentJob.status == status_filter)
    if peer_id:
        count_query = count_query.where(DeploymentJob.peer_id == peer_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return DeploymentJobListResponse(
        items=[
            DeploymentJobResponse(
                id=j.id,
                peer_id=j.peer_id,
                job_type=j.job_type,
                status=j.status,
                progress_percent=j.progress_percent,
                started_at=j.started_at,
                completed_at=j.completed_at,
                error_message=j.error_message,
                operations_log=j.operations_log,
                created_at=j.created_at,
                created_by_id=j.created_by_id,
            )
            for j in jobs
        ],
        total=total,
    )


@router.get("/{job_id}", response_model=DeploymentJobDetailResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific deployment job with details."""
    result = await db.execute(
        select(DeploymentJob)
        .options(selectinload(DeploymentJob.api_call_logs))
        .where(DeploymentJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment job not found",
        )

    return DeploymentJobDetailResponse(
        id=job.id,
        peer_id=job.peer_id,
        job_type=job.job_type,
        status=job.status,
        progress_percent=job.progress_percent,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        operations_log=job.operations_log,
        created_at=job.created_at,
        created_by_id=job.created_by_id,
        api_call_logs=[
            ApiCallLogResponse(
                id=log.id,
                method=log.method,
                endpoint=log.endpoint,
                request_body=log.request_body,
                response_status=log.response_status,
                response_body=log.response_body,
                error_message=log.error_message,
                timestamp=log.timestamp,
            )
            for log in job.api_call_logs
        ],
    )


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending or running deployment job."""
    result = await db.execute(
        select(DeploymentJob).where(DeploymentJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment job not found",
        )

    if job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {job.status.value}",
        )

    job.status = JobStatus.CANCELLED
    await db.commit()

    return {"message": "Job cancelled", "job_id": job.id}


@router.post("/{job_id}/retry")
async def retry_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed deployment job."""
    result = await db.execute(
        select(DeploymentJob).where(DeploymentJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment job not found",
        )

    if job.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only retry failed jobs",
        )

    # Import here to avoid circular imports
    from app.services.deployment import DeploymentService

    deployment_service = DeploymentService(db)
    new_job = await deployment_service.deploy_configuration(
        job.peer_id,
        job.created_by_id,
    )

    return {
        "message": "New deployment job created",
        "original_job_id": job.id,
        "new_job_id": new_job.id,
    }


@router.get("/{job_id}/logs")
async def get_job_logs(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed API call logs for a deployment job."""
    result = await db.execute(
        select(DeploymentJob)
        .options(selectinload(DeploymentJob.api_call_logs))
        .where(DeploymentJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment job not found",
        )

    return {
        "job_id": job.id,
        "logs": [
            {
                "id": log.id,
                "method": log.method.value,
                "endpoint": log.endpoint,
                "request_body": log.request_body,
                "response_status": log.response_status,
                "response_body": log.response_body,
                "error_message": log.error_message,
                "timestamp": log.timestamp.isoformat(),
            }
            for log in job.api_call_logs
        ],
        "total": len(job.api_call_logs),
    }


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a deployment job (must not be running or pending)."""
    result = await db.execute(
        select(DeploymentJob).where(DeploymentJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment job not found",
        )

    if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a pending or running job. Cancel it first.",
        )

    await db.delete(job)
    await db.commit()
