"""
Shared services for LANbu Handy
"""

from app.model_service import ModelService
from app.printer_service import PrinterService
from app.slice_progress_service import slice_progress_service
from app.slicer_service import BambuStudioCLIWrapper
from app.thumbnail_service import ThumbnailService
from app.upload_progress_service import upload_progress_service

# Initialize services once
model_service = ModelService()
printer_service = PrinterService()
thumbnail_service = ThumbnailService()
slicer_service = BambuStudioCLIWrapper()

# Progress services
upload_progress_service = upload_progress_service
slice_progress_service = slice_progress_service
