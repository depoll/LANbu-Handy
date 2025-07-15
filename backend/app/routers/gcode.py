"""
G-code file router for LANbu Handy.

This module handles G-code file operations including downloading generated files.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.utils import get_gcode_output_dir

# Initialize logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/gcode", tags=["gcode"])


@router.get("/download/{file_name}")
async def download_gcode(file_name: str):
    """
    Download a generated G-code file.
    This endpoint allows users to download G-code files that have been generated
    by the slicing process. For security, it validates that the file exists in
    the designated G-code output directory.
    Args:
        file_name: The name of the G-code file to download (not a full path)
    Returns:
        FileResponse with the G-code file as a download
    Raises:
        HTTPException: If file not found or access denied
    """
    try:
        # Get the G-code output directory
        gcode_dir = get_gcode_output_dir()

        # Construct the file path (security: don't allow path traversal)
        if "/" in file_name or "\\" in file_name or ".." in file_name:
            raise HTTPException(
                status_code=400, detail="Invalid file name - path traversal not allowed"
            )

        file_path = gcode_dir / file_name

        # Verify the file exists and is within the gcode directory
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(
                status_code=404, detail=f"G-code file not found: {file_name}"
            )

        # Verify the file is actually in the gcode directory (security check)
        try:
            file_path.resolve().relative_to(gcode_dir.resolve())
        except ValueError:
            raise HTTPException(
                status_code=403, detail="Access denied - file outside allowed directory"
            )

        # Determine media type based on file extension
        if file_name.lower().endswith((".gcode", ".gcode.3mf")):
            if file_name.lower().endswith(".gcode.3mf"):
                media_type = "application/octet-stream"
            else:
                media_type = "text/plain"
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type - only .gcode and .gcode.3mf files allowed",
            )

        # Return the file as a download
        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=file_name,
            headers={"Content-Disposition": f"attachment; filename={file_name}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading G-code file: {e}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error downloading file: {str(e)}"
        )