"""
Model management endpoints for LANbu Handy
"""

import logging

from app.model_schemas import (
    ModelDownloadError,
    ModelValidationError,
)
from app.schemas import (
    FilamentRequirementResponse,
    ModelSubmissionResponse,
    ModelURLRequest,
    PlateInfoResponse,
)

# Import services from services module for test compatibility
from app.services import model_service, thumbnail_service
from app.thumbnail_service import ThumbnailGenerationError
from app.utils import handle_model_errors
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/model", tags=["models"])


@router.post("/submit-url", response_model=ModelSubmissionResponse)
async def submit_model_url(request: ModelURLRequest):
    """
    Submit a model URL for download and validation.

    Accepts a JSON payload containing a model_url string, downloads the file,
    validates it, and stores it temporarily for processing.

    Args:
        request: ModelURLRequest containing the model_url

    Returns:
        ModelSubmissionResponse with success status and file information

    Raises:
        HTTPException: If validation or download fails
    """
    try:
        # Download and validate the model
        file_path = await model_service.download_model(request.model_url)

        # Parse comprehensive model information (may convert STL to 3MF)
        model_info, final_file_path = model_service.parse_3mf_model_info(file_path)

        # Update file_path to point to the actual file (potentially converted to 3MF)
        file_path = final_file_path

        # Get file information (using potentially updated file_path)
        file_info = model_service.get_file_info(file_path)

        # Convert filament requirements to response model if found
        filament_requirements_response = None
        if model_info.filament_requirements:
            filament_requirements_response = FilamentRequirementResponse(
                filament_count=model_info.filament_requirements.filament_count,
                filament_types=model_info.filament_requirements.filament_types,
                filament_colors=model_info.filament_requirements.filament_colors,
                has_multicolor=model_info.filament_requirements.has_multicolor,
            )

        # Convert plate information to response model
        plates_response = []
        if model_info.plates:
            for plate in model_info.plates:
                plates_response.append(
                    PlateInfoResponse(
                        index=plate.index,
                        name=plate.name,
                        prediction_seconds=plate.prediction_seconds,
                        weight_grams=plate.weight_grams,
                        has_support=plate.has_support,
                        object_count=plate.object_count,
                    )
                )

        # Generate file ID (using the actual filename after any conversion)
        file_id = file_path.name

        # Extract original filename (remove UUID prefix)
        # Format is: {uuid}_{original_filename}
        original_filename = file_id.split("_", 1)[1] if "_" in file_id else file_id

        return ModelSubmissionResponse(
            success=True,
            message="Model downloaded and validated successfully",
            file_id=file_id,
            original_filename=original_filename,
            file_info=file_info,
            filament_requirements=filament_requirements_response,
            plates=plates_response if plates_response else None,
            has_multiple_plates=model_info.has_multiple_plates,
        )

    except (ModelValidationError, ModelDownloadError, Exception) as e:
        raise handle_model_errors(e)


@router.post("/upload-file", response_model=ModelSubmissionResponse)
async def upload_model_file(file: UploadFile = File(...)):
    """
    Upload a model file for validation and processing.

    Accepts a file upload (multipart/form-data) containing a 3D model file,
    validates it, and stores it temporarily for processing.

    Args:
        file: UploadFile containing the 3D model file (.stl or .3mf)

    Returns:
        ModelSubmissionResponse with success status and file information

    Raises:
        HTTPException: If validation fails or upload processing fails
    """
    try:
        # Validate file extension
        if not file.filename:
            raise ModelValidationError("No filename provided")

        if not model_service.validate_file_extension(file.filename):
            extensions = ", ".join(model_service.supported_extensions)
            raise ModelValidationError(
                f"Unsupported file extension. File must be one of: {extensions}"
            )

        # Check file size (FastAPI doesn't provide direct size, so we'll
        # check during read)
        content = await file.read()

        if len(content) > model_service.max_file_size_bytes:
            max_mb = model_service.max_file_size_bytes // (1024 * 1024)
            raise ModelValidationError(
                f"File size exceeds maximum allowed size of {max_mb}MB"
            )

        # Generate unique filename and save to temp directory
        import uuid

        unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
        temp_file_path = model_service.temp_dir / unique_filename

        # Write uploaded content to temporary file
        with open(temp_file_path, "wb") as f:
            f.write(content)

        # Parse comprehensive model information (may convert STL to 3MF)
        model_info, final_file_path = model_service.parse_3mf_model_info(temp_file_path)

        # Update temp_file_path to point to the actual file (converted to 3MF)
        temp_file_path = final_file_path

        # Get file information (using potentially updated file_path)
        file_info = model_service.get_file_info(temp_file_path)

        # Convert filament requirements to response model if found
        filament_requirements_response = None
        if model_info.filament_requirements:
            filament_requirements_response = FilamentRequirementResponse(
                filament_count=model_info.filament_requirements.filament_count,
                filament_types=model_info.filament_requirements.filament_types,
                filament_colors=model_info.filament_requirements.filament_colors,
                has_multicolor=model_info.filament_requirements.has_multicolor,
            )

        # Convert plate information to response model
        plates_response = []
        if model_info.plates:
            for plate in model_info.plates:
                plates_response.append(
                    PlateInfoResponse(
                        index=plate.index,
                        name=plate.name,
                        prediction_seconds=plate.prediction_seconds,
                        weight_grams=plate.weight_grams,
                        has_support=plate.has_support,
                        object_count=plate.object_count,
                    )
                )

        # Generate file ID (using the actual filename after any conversion)
        file_id = temp_file_path.name

        return ModelSubmissionResponse(
            success=True,
            message="Model uploaded and validated successfully",
            file_id=file_id,
            original_filename=file.filename,
            file_info=file_info,
            filament_requirements=filament_requirements_response,
            plates=plates_response if plates_response else None,
            has_multiple_plates=model_info.has_multiple_plates,
        )

    except (ModelValidationError, Exception) as e:
        raise handle_model_errors(e)


@router.get("/{file_id}/plate/{plate_index}/filament-requirements")
async def get_plate_filament_requirements(file_id: str, plate_index: int):
    """
    Get filament requirements for a specific plate.

    Returns simplified filament requirements for the specified plate rather than
    the full model requirements. This helps users focus on only the filaments
    needed for their selected plate in multi-plate models.

    Args:
        file_id: The file ID from model submission
        plate_index: The index of the plate to get requirements for

    Returns:
        FilamentRequirementResponse with plate-specific requirements

    Raises:
        HTTPException: If file is not found or plate index is invalid
    """
    try:
        # Find the model file in the temp directory
        model_file_path = model_service.temp_dir / file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {file_id}"
            )

        # Validate file extension for security
        if not model_service.validate_file_extension(model_file_path.name):
            raise HTTPException(
                status_code=400, detail="Invalid file type for plate requirements"
            )

        # Get plate-specific filament requirements
        plate_requirements = model_service.get_plate_specific_filament_requirements(
            model_file_path, plate_index
        )

        if not plate_requirements:
            raise HTTPException(
                status_code=404,
                detail=f"No filament requirements found for plate {plate_index}",
            )

        # Convert to response format
        requirements_response = FilamentRequirementResponse(
            filament_count=plate_requirements.filament_count,
            filament_types=plate_requirements.filament_types,
            filament_colors=plate_requirements.filament_colors,
            has_multicolor=plate_requirements.has_multicolor,
        )

        return {
            "success": True,
            "message": f"Filament requirements for plate {plate_index}",
            "plate_index": plate_index,
            "filament_requirements": requirements_response,
            "is_filtered": True,  # Indicates this is a filtered/estimated set
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error getting plate filament requirements: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@router.get("/preview/{file_id}")
async def get_model_preview(file_id: str):
    """
    Serve a model file for preview rendering.

    Returns the raw model file content for client-side 3D rendering.
    Supports both STL and 3MF files for Three.js preview.
    For 3MF files, automatically repairs Bambu Studio format for better
    Three.js compatibility.

    Args:
        file_id: The file ID from model submission

    Returns:
        FileResponse with the model file content (repaired if 3MF)

    Raises:
        HTTPException: If file is not found or access is denied
    """
    try:
        # Find the model file in the temp directory
        model_file_path = model_service.temp_dir / file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {file_id}"
            )

        # Validate file extension for security
        if not model_service.validate_file_extension(model_file_path.name):
            raise HTTPException(status_code=400, detail="Invalid file type for preview")

        # Serve the file based on its type
        if model_file_path.suffix.lower() == ".3mf":
            media_type = "model/3mf"
        elif model_file_path.suffix.lower() == ".stl":
            media_type = "model/stl"
        else:
            media_type = "application/octet-stream"

        return FileResponse(
            path=model_file_path,
            media_type=media_type,
            filename=model_file_path.name,
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error serving model preview: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@router.get("/thumbnail/{file_id}")
async def get_model_thumbnail(file_id: str, width: int = 300, height: int = 300):
    """
    Generate and serve a thumbnail image for a model file.

    This endpoint generates a thumbnail image for the specified model file using
    the slicer as a fallback when Three.js previews fail or for complex models.
    Thumbnails are cached and reused for subsequent requests.

    Args:
        file_id: The file ID from model submission
        width: Thumbnail width in pixels (default: 300)
        height: Thumbnail height in pixels (default: 300)

    Returns:
        FileResponse with the thumbnail image (PNG or SVG)

    Raises:
        HTTPException: If file is not found or thumbnail generation fails
    """
    try:
        # Debug logging
        logger.info(
            f"Thumbnail request: file_id='{file_id}', width={width}, height={height}"
        )

        # Find the model file in the temp directory
        model_file_path = model_service.temp_dir / file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {file_id}"
            )

        # Validate file extension for security
        if not model_service.validate_file_extension(model_file_path.name):
            raise HTTPException(
                status_code=400, detail="Invalid file type for thumbnail"
            )

        # Always try to generate/extract thumbnail to ensure we get the best quality
        # For 3MF files, this will extract embedded thumbnails
        # For other files or when extraction fails, it will use CLI or placeholders
        logger.info(f"Generating thumbnail for: {file_id}")
        thumbnail_path = thumbnail_service.generate_thumbnail(
            model_file_path, width=width, height=height, prefer_embedded=True
        )
        size_info = thumbnail_path.stat().st_size if thumbnail_path.exists() else "N/A"
        logger.info(
            f"Thumbnail result: {thumbnail_path}, exists: {thumbnail_path.exists()}, "
            f"size: {size_info}"
        )

        # Determine media type based on file extension
        media_type = "image/png"
        if thumbnail_path.suffix.lower() == ".svg":
            media_type = "image/svg+xml"

        return FileResponse(
            path=thumbnail_path,
            media_type=media_type,
            filename=f"{model_file_path.stem}_thumbnail{thumbnail_path.suffix}",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ThumbnailGenerationError as e:
        raise HTTPException(
            status_code=500, detail=f"Thumbnail generation failed: {str(e)}"
        )
    except Exception as e:
        msg = f"Internal server error generating thumbnail: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@router.get("/thumbnail/{file_id}/plate/{plate_index}")
async def get_plate_thumbnail(
    file_id: str, plate_index: int, width: int = 300, height: int = 300
):
    """
    Generate and serve a thumbnail image for a specific plate in a model file.

    This endpoint extracts or generates a thumbnail for a specific plate from
    a 3MF file. Falls back to general thumbnail if plate-specific not available.

    Args:
        file_id: Unique identifier for the downloaded model file
        plate_index: Index of the plate (0-based)
        width: Thumbnail width in pixels (default: 300)
        height: Thumbnail height in pixels (default: 300)

    Returns:
        FileResponse with the thumbnail image (PNG or SVG)

    Raises:
        HTTPException: If file is not found or thumbnail generation fails
    """
    try:
        # Find the model file in the temp directory
        model_file_path = model_service.temp_dir / file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {file_id}"
            )

        # Validate file extension for security
        if not model_service.validate_file_extension(model_file_path.name):
            raise HTTPException(
                status_code=400, detail="Invalid file type for thumbnail"
            )

        # Generate plate-specific thumbnail path
        thumbnail_name = f"{model_file_path.stem}_plate_{plate_index}_thumbnail.png"
        thumbnail_path = thumbnail_service.temp_dir / thumbnail_name

        # Check if plate-specific thumbnail already exists
        if thumbnail_path.exists():
            logger.debug(f"Using existing plate thumbnail: {thumbnail_path}")
        else:
            # Extract/generate plate-specific thumbnail
            logger.info(f"Generating plate {plate_index} thumbnail for: {file_id}")
            extracted_path = thumbnail_service.extract_plate_thumbnail(
                model_file_path, plate_index, thumbnail_path
            )

            if not extracted_path or not extracted_path.exists():
                # Fallback to general thumbnail generation with embedded preference
                thumbnail_path = thumbnail_service.generate_thumbnail(
                    model_file_path, thumbnail_path, width, height, prefer_embedded=True
                )

        # Determine media type based on file extension
        media_type = "image/png"
        if thumbnail_path.suffix.lower() == ".svg":
            media_type = "image/svg+xml"

        return FileResponse(
            path=thumbnail_path,
            media_type=media_type,
            filename=(
                f"{model_file_path.stem}_plate_{plate_index}_thumbnail"
                f"{thumbnail_path.suffix}"
            ),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error generating plate thumbnail: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@router.get("/thumbnails/{file_id}")
async def get_available_thumbnails(file_id: str):
    """
    Get information about available thumbnails in a model file.

    This endpoint analyzes a 3MF file and returns information about
    available general and plate-specific thumbnails.

    Args:
        file_id: Unique identifier for the downloaded model file

    Returns:
        Dictionary with thumbnail availability information

    Raises:
        HTTPException: If file is not found
    """
    try:
        # Find the model file in the temp directory
        model_file_path = model_service.temp_dir / file_id

        if not model_file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Model file not found: {file_id}"
            )

        # Validate file extension for security
        if not model_service.validate_file_extension(model_file_path.name):
            raise HTTPException(
                status_code=400, detail="Invalid file type for thumbnail analysis"
            )

        # Analyze available thumbnails
        thumbnail_info = thumbnail_service.get_available_thumbnails(model_file_path)

        return {
            "file_id": file_id,
            "file_type": model_file_path.suffix.lower(),
            "thumbnails": thumbnail_info,
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        msg = f"Internal server error analyzing thumbnails: {str(e)}"
        raise HTTPException(status_code=500, detail=msg)


@router.get("/debug-thumbnail/{file_id}")
async def debug_thumbnail_extraction(file_id: str):
    """
    Debug endpoint to test thumbnail extraction step by step.
    """
    try:
        # Find the model file in the temp directory
        model_file_path = model_service.temp_dir / file_id

        if not model_file_path.exists():
            return {
                "error": f"Model file not found: {file_id}",
                "path": str(model_file_path),
            }

        debug_info = {
            "file_id": file_id,
            "file_path": str(model_file_path),
            "file_exists": model_file_path.exists(),
            "file_size": (
                model_file_path.stat().st_size if model_file_path.exists() else 0
            ),
            "file_extension": model_file_path.suffix.lower(),
            "is_3mf": model_file_path.suffix.lower() == ".3mf",
        }

        if model_file_path.suffix.lower() == ".3mf":
            # Test thumbnail extraction
            import zipfile

            try:
                with zipfile.ZipFile(model_file_path, "r") as zip_file:
                    files = zip_file.namelist()

                    # Categorize all files for better debugging
                    metadata_files = [f for f in files if f.startswith("Metadata/")]
                    auxiliaries_files = [
                        f for f in files if f.startswith("Auxiliaries/")
                    ]
                    thumbnail_files = [
                        f
                        for f in files
                        if "thumbnail" in f.lower() and f.lower().endswith(".png")
                    ]
                    image_files = [
                        f
                        for f in files
                        if any(
                            ext in f.lower()
                            for ext in [".png", ".jpg", ".jpeg", ".bmp"]
                        )
                    ]

                    debug_info.update(
                        {
                            "zip_files_count": len(files),
                            "all_files": files[:20],  # Show first 20 files
                            "metadata_files": metadata_files,
                            "auxiliaries_files": auxiliaries_files,
                            "thumbnail_files": thumbnail_files,
                            "all_image_files": image_files,
                        }
                    )

                    if thumbnail_files:
                        # Try to extract the first thumbnail we find
                        test_thumb = thumbnail_files[0]
                        test_output = (
                            thumbnail_service.temp_dir / f"debug_{file_id}_thumb.png"
                        )

                        with zip_file.open(test_thumb) as thumb_file:
                            content = thumb_file.read()
                            with open(test_output, "wb") as out_file:
                                out_file.write(content)

                        debug_info["extraction_test"] = {
                            "extracted_file": test_thumb,
                            "output_path": str(test_output),
                            "output_exists": test_output.exists(),
                            "output_size": len(content),
                            "content_length": len(content),
                        }

                    # Also test our specific metadata paths
                    metadata_thumbs = [
                        f
                        for f in files
                        if f.startswith("Metadata/") and "thumbnail" in f.lower()
                    ]
                    debug_info["metadata_thumbnails"] = metadata_thumbs

            except Exception as e:
                debug_info["zip_error"] = str(e)

        # Test thumbnail availability analysis
        try:
            available_thumbs = thumbnail_service.get_available_thumbnails(
                model_file_path
            )
            debug_info["available_thumbnails"] = available_thumbs
        except Exception as e:
            debug_info["thumbnail_analysis_error"] = str(e)

        # Test plate-specific thumbnail extraction
        try:
            debug_info["plate_extractions"] = {}
            # Test first few plates
            for plate_idx in [1, 2, 3]:
                plate_result = thumbnail_service.extract_plate_thumbnail(
                    model_file_path, plate_idx
                )
                if plate_result and plate_result.exists():
                    debug_info["plate_extractions"][plate_idx] = {
                        "path": str(plate_result),
                        "size": plate_result.stat().st_size,
                    }
                else:
                    debug_info["plate_extractions"][plate_idx] = None
        except Exception as e:
            debug_info["plate_extraction_error"] = str(e)

        # Test the actual thumbnail service
        try:
            # First, clear any existing thumbnail to force regeneration
            existing_thumb = thumbnail_service.get_thumbnail_path(model_file_path)
            if existing_thumb.exists():
                existing_thumb.unlink()
                debug_info["cleared_existing"] = str(existing_thumb)

            result_path = thumbnail_service.generate_thumbnail(
                model_file_path, prefer_embedded=True
            )
            debug_info["service_result"] = {
                "path": str(result_path),
                "exists": result_path.exists(),
                "size": result_path.stat().st_size if result_path.exists() else 0,
            }
        except Exception as e:
            debug_info["service_error"] = str(e)

        return debug_info

    except Exception as e:
        return {"error": f"Debug failed: {str(e)}"}
