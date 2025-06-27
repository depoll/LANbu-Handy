"""
Upload progress tracking service for FTP uploads.

This service provides a simple way to track and retrieve upload progress
for FTP file transfers.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class UploadProgress:
    """Progress information for an upload."""

    filename: str
    total_size: int
    uploaded_size: int = 0
    percent: int = 0
    status: str = "pending"  # pending, uploading, completed, error
    message: str = ""
    remote_path: str = ""
    started_at: float = 0
    completed_at: float = 0

    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        if self.started_at == 0:
            return 0
        end_time = self.completed_at if self.completed_at > 0 else time.time()
        return end_time - self.started_at

    @property
    def upload_speed(self) -> float:
        """Get upload speed in MB/s."""
        if self.elapsed_time == 0 or self.uploaded_size == 0:
            return 0
        return (self.uploaded_size / (1024 * 1024)) / self.elapsed_time


class UploadProgressService:
    """Service for tracking upload progress."""

    def __init__(self):
        self._progress: Dict[str, UploadProgress] = {}
        self._lock = asyncio.Lock()

    async def start_upload(
        self, upload_id: str, filename: str, total_size: int
    ) -> None:
        """Start tracking a new upload."""
        async with self._lock:
            self._progress[upload_id] = UploadProgress(
                filename=filename,
                total_size=total_size,
                status="uploading",
                message=f"Starting upload of {filename}",
                started_at=time.time(),
            )
            logger.info(
                f"Started tracking upload {upload_id}: {filename} ({total_size} bytes)"
            )

    async def update_progress(self, upload_id: str, percent: int, message: str) -> None:
        """Update progress for an upload."""
        async with self._lock:
            if upload_id in self._progress:
                progress = self._progress[upload_id]
                progress.percent = percent
                progress.message = message
                progress.uploaded_size = int(progress.total_size * (percent / 100))

                # Update status if completed
                if percent >= 100:
                    progress.status = "completed"
                    progress.completed_at = time.time()

                logger.debug(
                    f"Updated progress for {upload_id}: {percent}% - {message}"
                )

    async def set_error(self, upload_id: str, error_message: str) -> None:
        """Mark an upload as failed."""
        async with self._lock:
            if upload_id in self._progress:
                progress = self._progress[upload_id]
                progress.status = "error"
                progress.message = error_message
                progress.completed_at = time.time()
                logger.error(f"Upload {upload_id} failed: {error_message}")

    async def set_completed(self, upload_id: str, remote_path: str) -> None:
        """Mark an upload as completed."""
        async with self._lock:
            if upload_id in self._progress:
                progress = self._progress[upload_id]
                progress.status = "completed"
                progress.percent = 100
                progress.uploaded_size = progress.total_size
                progress.remote_path = remote_path
                progress.message = f"Upload complete: {remote_path}"
                progress.completed_at = time.time()
                logger.info(f"Upload {upload_id} completed: {remote_path}")

    async def get_progress(self, upload_id: str) -> Optional[UploadProgress]:
        """Get progress for an upload."""
        async with self._lock:
            return self._progress.get(upload_id)

    async def cleanup_old_uploads(self, max_age_seconds: int = 3600) -> None:
        """Remove old upload records."""
        async with self._lock:
            current_time = time.time()
            to_remove = []

            for upload_id, progress in self._progress.items():
                if progress.status in ["completed", "error"]:
                    age = current_time - (progress.completed_at or progress.started_at)
                    if age > max_age_seconds:
                        to_remove.append(upload_id)

            for upload_id in to_remove:
                del self._progress[upload_id]
                logger.debug(f"Cleaned up old upload record: {upload_id}")


# Global instance
upload_progress_service = UploadProgressService()
