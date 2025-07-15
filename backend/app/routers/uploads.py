"""
Upload progress router for LANbu Handy.

This module handles upload progress tracking for file operations.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.upload_progress_service import UploadProgressService

# Initialize logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/upload", tags=["uploads"])

# Initialize service (will be injected by dependency injection in main.py)
upload_progress_service: Optional[UploadProgressService] = None


def set_service(upload_svc: UploadProgressService):
    """Set the service instance (called from main.py)."""
    global upload_progress_service
    upload_progress_service = upload_svc


@router.get("/progress/{upload_id}")
async def get_upload_progress(upload_id: str):
    """
    Get the current progress of a file upload.
    Args:
        upload_id: The upload ID returned from the print job
    Returns:
        Upload progress information including percent, status, and file location
    Raises:
        HTTPException: If upload ID is not found
    """
    progress = await upload_progress_service.get_progress(upload_id)
    if not progress:
        raise HTTPException(
            status_code=404, detail=f"Upload progress not found for ID: {upload_id}"
        )

    return {
        "upload_id": upload_id,
        "filename": progress.filename,
        "total_size": progress.total_size,
        "uploaded_size": progress.uploaded_size,
        "percent": progress.percent,
        "status": progress.status,
        "message": progress.message,
        "remote_path": progress.remote_path,
        "elapsed_time": progress.elapsed_time,
        "upload_speed_mbps": progress.upload_speed,
    }