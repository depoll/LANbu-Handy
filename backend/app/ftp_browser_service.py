"""
FTP browser service for LANbu Handy.

Provides file browsing, downloading, and thumbnail extraction for files
stored on Bambu Lab printers' SD cards via FTP.
"""

import io
import logging
import mimetypes
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.ftp_curl_wrapper import CurlFTPSClient
from app.printer_config import PrinterConfig
from app.upload_progress_service import UploadProgressService
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Information about a file on the printer."""

    name: str
    path: str
    type: str  # "file" or "directory"
    size: int
    modified: str
    mime_type: Optional[str] = None
    is_printable: bool = False
    has_thumbnail: bool = False


class FTPBrowserService:
    """Service for browsing and downloading files from printer FTP."""

    def __init__(self, upload_progress_service: UploadProgressService):
        self.upload_progress_service = upload_progress_service
        self._ftp_clients: Dict[str, CurlFTPSClient] = {}

    def _get_ftp_client(self, printer_config: PrinterConfig) -> CurlFTPSClient:
        """Get or create FTP client for a printer."""
        printer_id = printer_config.canonical_id
        if printer_id not in self._ftp_clients:
            self._ftp_clients[printer_id] = CurlFTPSClient(
                host=printer_config.ip,
                password=printer_config.access_code,
                timeout=30,
            )
        return self._ftp_clients[printer_id]

    def _determine_file_info(self, file_dict: dict, base_path: str) -> FileInfo:
        """Convert raw file info to FileInfo object with additional metadata."""
        name = file_dict["name"]
        # Ensure consistent path construction
        if base_path and base_path != "/":
            # Remove trailing slash from base_path and add single separator
            full_path = f"{base_path.rstrip('/')}/{name}"
        else:
            # For root directory, just use the name
            full_path = name

        # Determine MIME type
        mime_type = None
        if file_dict["type"] == "file":
            mime_type, _ = mimetypes.guess_type(name)

        # Determine if file is printable
        is_printable = False
        has_thumbnail = False
        if file_dict["type"] == "file":
            lower_name = name.lower()
            if lower_name.endswith((".gcode", ".3mf")):
                is_printable = True
            if lower_name.endswith((".3mf", ".gcode")):
                has_thumbnail = True  # We'll try to extract thumbnail
            # Check for video files that might have thumbnails
            if lower_name.endswith((".mp4", ".avi")):
                has_thumbnail = True  # We'll check for thumbnail in nested folder

        return FileInfo(
            name=name,
            path=full_path,
            type=file_dict["type"],
            size=file_dict.get("size", 0),
            modified=file_dict.get("modified", ""),
            mime_type=mime_type,
            is_printable=is_printable,
            has_thumbnail=has_thumbnail,
        )

    def list_files(
        self, printer_config: PrinterConfig, path: str = ""
    ) -> Tuple[bool, List[FileInfo], Optional[str]]:
        """
        List files in a directory on the printer.

        Args:
            printer_config: Printer configuration
            path: Directory path (empty for root)

        Returns:
            Tuple of (success, list of FileInfo, error_message)
        """
        try:
            logger.info(f"FTPBrowserService.list_files called with path='{path}'")
            client = self._get_ftp_client(printer_config)

            # Get detailed file listing
            success, file_list = client.list_directory_details(path)

            if not success:
                return False, [], "Failed to list directory"

            # Convert to FileInfo objects
            files = []
            for file_dict in file_list:
                try:
                    file_info = self._determine_file_info(file_dict, path)
                    files.append(file_info)
                except Exception as e:
                    logger.warning(f"Error processing file {file_dict}: {e}")
                    continue

            # Sort: directories first, then by name
            files.sort(key=lambda f: (f.type != "directory", f.name.lower()))

            return True, files, None

        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return False, [], str(e)

    def download_file(
        self,
        printer_config: PrinterConfig,
        remote_path: str,
        session_id: str,
    ) -> Tuple[bool, Optional[Path], Optional[str]]:
        """
        Download a file from the printer to a temporary location.

        Args:
            printer_config: Printer configuration
            remote_path: Remote file path
            session_id: Session ID for progress tracking

        Returns:
            Tuple of (success, local_path, error_message)
        """
        try:
            client = self._get_ftp_client(printer_config)

            # Create temporary file
            suffix = Path(remote_path).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                local_path = Path(temp_file.name)

            # Progress callback - skip for now due to async/sync mismatch
            def progress_callback(percent: int, message: str):
                # TODO: Fix async progress updates
                logger.debug(f"Download progress: {percent}% - {message}")

            # Download the file
            success, message = client.download_file(
                remote_path, str(local_path), progress_callback
            )

            if success:
                return True, local_path, None
            else:
                # Clean up on failure
                if local_path.exists():
                    local_path.unlink()
                return False, None, message

        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return False, None, str(e)

    def extract_3mf_thumbnail(
        self, file_path: Path
    ) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """
        Extract thumbnail from a 3MF file.

        Args:
            file_path: Path to 3MF file

        Returns:
            Tuple of (success, thumbnail_bytes, error_message)
        """
        try:
            with zipfile.ZipFile(file_path, "r") as zip_file:
                # Look for thumbnail in standard locations
                thumbnail_paths = [
                    "Metadata/thumbnail.png",
                    "Metadata/thumbnail.jpg",
                    "Metadata/thumbnail.jpeg",
                    "thumbnail.png",
                    "thumbnail.jpg",
                ]

                for thumb_path in thumbnail_paths:
                    try:
                        with zip_file.open(thumb_path) as thumb_file:
                            thumbnail_data = thumb_file.read()

                            # Optionally resize if too large
                            img = Image.open(io.BytesIO(thumbnail_data))
                            if img.width > 400 or img.height > 400:
                                img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                                output = io.BytesIO()
                                img.save(output, format="PNG")
                                thumbnail_data = output.getvalue()

                            return True, thumbnail_data, None
                    except KeyError:
                        continue

                return False, None, "No thumbnail found in 3MF file"

        except Exception as e:
            logger.error(f"Error extracting thumbnail: {e}")
            return False, None, str(e)

    def extract_gcode_thumbnail(
        self, file_path: Path
    ) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """
        Extract thumbnail from a G-code file.

        Bambu Studio embeds base64-encoded thumbnails in gcode comments.

        Args:
            file_path: Path to G-code file

        Returns:
            Tuple of (success, thumbnail_bytes, error_message)
        """
        try:
            import base64
            import re

            # Read the first part of the gcode file (thumbnails are at the beginning)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                # Read first 100KB which should contain thumbnail
                content = f.read(102400)

            # Look for thumbnail patterns
            # Bambu Studio format: ; thumbnail begin 96x96 size_in_bytes
            thumbnail_pattern = r"; thumbnail begin \d+x\d+ \d+\n(.*?)\n; thumbnail end"
            matches = re.findall(thumbnail_pattern, content, re.DOTALL)

            if matches:
                # Get the largest thumbnail (usually the last one)
                thumbnail_data = matches[-1]

                # Remove comment semicolons and join lines
                lines = thumbnail_data.strip().split("\n")
                base64_data = "".join(line.strip().lstrip("; ") for line in lines)

                # Decode base64
                image_data = base64.b64decode(base64_data)

                # Resize if needed
                img = Image.open(io.BytesIO(image_data))
                if img.width > 400 or img.height > 400:
                    img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    img.save(output, format="PNG")
                    image_data = output.getvalue()

                return True, image_data, None

            return False, None, "No thumbnail found in G-code file"

        except Exception as e:
            logger.error(f"Error extracting G-code thumbnail: {e}")
            return False, None, str(e)

    def get_file_thumbnail(
        self,
        printer_config: PrinterConfig,
        remote_path: str,
        session_id: str,
    ) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """
        Get thumbnail for a file (supports 3MF and video files).

        Args:
            printer_config: Printer configuration
            remote_path: Remote file path
            session_id: Session ID for progress tracking

        Returns:
            Tuple of (success, thumbnail_bytes, error_message)
        """
        try:
            lower_path = remote_path.lower()

            # Handle 3MF and G-code files
            if lower_path.endswith((".3mf", ".gcode")):
                # Download the file first
                success, local_path, error = self.download_file(
                    printer_config, remote_path, session_id
                )

                if not success:
                    return False, None, error

                try:
                    # Extract thumbnail based on file type
                    if lower_path.endswith(".3mf"):
                        success, thumbnail, error = self.extract_3mf_thumbnail(
                            local_path
                        )
                    else:  # .gcode
                        success, thumbnail, error = self.extract_gcode_thumbnail(
                            local_path
                        )
                    return success, thumbnail, error
                finally:
                    # Clean up temporary file
                    if local_path and local_path.exists():
                        local_path.unlink()

            # Handle video files - look for thumbnail in nested folder
            elif lower_path.endswith((".mp4", ".avi")):
                # Get the directory and filename
                path_parts = remote_path.split("/")
                if len(path_parts) > 1:
                    directory = "/".join(path_parts[:-1])
                    filename = path_parts[-1]
                else:
                    directory = ""
                    filename = remote_path

                # Remove extension and look for thumbnail
                base_name = filename.rsplit(".", 1)[0]
                thumbnail_path = f"{directory}/thumbnails/{base_name}.jpg"

                logger.info(f"Looking for video thumbnail at: {thumbnail_path}")

                # Try to download the thumbnail
                success, local_path, error = self.download_file(
                    printer_config, thumbnail_path, session_id
                )

                if success and local_path:
                    try:
                        # Read the thumbnail file
                        with open(local_path, "rb") as f:
                            thumbnail_data = f.read()

                        # Optionally resize if too large
                        img = Image.open(io.BytesIO(thumbnail_data))
                        if img.width > 400 or img.height > 400:
                            img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                            output = io.BytesIO()
                            img.save(output, format="JPEG")
                            thumbnail_data = output.getvalue()

                        return True, thumbnail_data, None
                    finally:
                        # Clean up
                        if local_path.exists():
                            local_path.unlink()
                else:
                    return False, None, f"No thumbnail found for video: {filename}"

            else:
                return (
                    False,
                    None,
                    f"Thumbnails not supported for file type: {remote_path}",
                )

        except Exception as e:
            logger.error(f"Error getting thumbnail: {e}")
            return False, None, str(e)

    def initiate_print_from_sd(
        self, printer_config: PrinterConfig, file_path: str
    ) -> Tuple[bool, str]:
        """
        Initiate printing a file from the SD card.

        Args:
            printer_config: Printer configuration
            file_path: Path to file on SD card

        Returns:
            Tuple of (success, message)
        """
        try:
            # Import PrinterService here to avoid circular imports
            from app.printer_service import PrinterService

            printer_service = PrinterService()

            # The file_path should be the full path on the SD card
            # For Bambu printers, SD card files are typically accessed
            # with their full path
            logger.info(f"Initiating print from SD card: {file_path}")

            # Use the printer service to send the print command
            # The printer expects the full SD card path as the filename
            result = printer_service.start_print(printer_config, file_path)

            if result.success:
                return True, f"Successfully started printing {file_path}"
            else:
                return False, result.message

        except Exception as e:
            logger.error(f"Error initiating print from SD: {e}")
            return False, f"Failed to start print: {str(e)}"
