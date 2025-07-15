"""Tests for FTP browser service."""

import io
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from app.ftp_browser_service import FTPBrowserService
from app.printer_config import PrinterConfig
from PIL import Image


@pytest.fixture
def mock_upload_progress_service():
    """Mock upload progress service."""
    service = Mock()
    service.update_progress = Mock()
    return service


@pytest.fixture
def ftp_browser_service(mock_upload_progress_service):
    """Create FTP browser service instance."""
    return FTPBrowserService(mock_upload_progress_service)


@pytest.fixture
def printer_config():
    """Create test printer configuration."""
    return PrinterConfig(
        name="Test Printer",
        ip="192.168.1.100",
        access_code="12345678",
        serial_number="TEST123",
    )


class TestFTPBrowserService:
    """Test FTP browser service functionality."""

    def test_determine_file_info_directory(self, ftp_browser_service):
        """Test file info determination for directories."""
        file_dict = {
            "name": "models",
            "type": "directory",
            "size": 0,
            "modified": "Jan 15 10:30",
        }

        file_info = ftp_browser_service._determine_file_info(file_dict, "/sdcard")

        assert file_info.name == "models"
        assert file_info.path == "/sdcard/models"
        assert file_info.type == "directory"
        assert not file_info.is_printable
        assert not file_info.has_thumbnail

    def test_determine_file_info_3mf_file(self, ftp_browser_service):
        """Test file info determination for 3MF files."""
        file_dict = {
            "name": "model.3mf",
            "type": "file",
            "size": 1024000,
            "modified": "Jan 15 10:30",
        }

        file_info = ftp_browser_service._determine_file_info(file_dict, "/sdcard")

        assert file_info.name == "model.3mf"
        assert file_info.path == "/sdcard/model.3mf"
        assert file_info.type == "file"
        assert file_info.is_printable
        assert file_info.has_thumbnail
        assert file_info.mime_type == "application/vnd.ms-3mfdocument"

    def test_determine_file_info_gcode_file(self, ftp_browser_service):
        """Test file info determination for G-code files."""
        file_dict = {
            "name": "print.gcode",
            "type": "file",
            "size": 2048000,
            "modified": "Jan 15 10:30",
        }

        file_info = ftp_browser_service._determine_file_info(file_dict, "/sdcard")

        assert file_info.name == "print.gcode"
        assert file_info.path == "/sdcard/print.gcode"
        assert file_info.type == "file"
        assert file_info.is_printable
        assert file_info.has_thumbnail  # We try to extract from gcode

    def test_determine_file_info_video_file(self, ftp_browser_service):
        """Test file info determination for video files."""
        file_dict = {
            "name": "timelapse.mp4",
            "type": "file",
            "size": 5000000,
            "modified": "Jan 15 10:30",
        }

        file_info = ftp_browser_service._determine_file_info(file_dict, "/sdcard")

        assert file_info.name == "timelapse.mp4"
        assert file_info.path == "/sdcard/timelapse.mp4"
        assert file_info.type == "file"
        assert not file_info.is_printable
        assert file_info.has_thumbnail  # We check for thumbnail in nested folder
        assert file_info.mime_type == "video/mp4"

    @patch("app.ftp_browser_service.CurlFTPSClient")
    def test_list_files_success(
        self, mock_curl_client, ftp_browser_service, printer_config
    ):
        """Test successful file listing."""
        # Mock FTP client
        mock_client = Mock()
        mock_curl_client.return_value = mock_client
        mock_client.list_directory_details.return_value = (
            True,
            [
                {
                    "name": "models",
                    "type": "directory",
                    "size": 0,
                    "modified": "Jan 15 10:30",
                    "permissions": "drwxr-xr-x",
                },
                {
                    "name": "test.3mf",
                    "type": "file",
                    "size": 1024000,
                    "modified": "Jan 15 10:30",
                    "permissions": "-rw-r--r--",
                },
            ],
        )

        success, files, error = ftp_browser_service.list_files(
            printer_config, "/sdcard"
        )

        assert success
        assert len(files) == 2
        assert files[0].name == "models"
        assert files[0].type == "directory"
        assert files[1].name == "test.3mf"
        assert files[1].is_printable
        assert error is None

    @patch("app.ftp_browser_service.CurlFTPSClient")
    def test_list_files_failure(
        self, mock_curl_client, ftp_browser_service, printer_config
    ):
        """Test failed file listing."""
        # Mock FTP client
        mock_client = Mock()
        mock_curl_client.return_value = mock_client
        mock_client.list_directory_details.return_value = (False, [])

        success, files, error = ftp_browser_service.list_files(
            printer_config, "/sdcard"
        )

        assert not success
        assert files == []
        assert error == "Failed to list directory"

    def test_extract_3mf_thumbnail(self, ftp_browser_service):
        """Test thumbnail extraction from 3MF file."""
        # Create a test 3MF file with thumbnail
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as tmp:
            with zipfile.ZipFile(tmp, "w") as zf:
                # Create a small test image
                img = Image.new("RGB", (100, 100), color="red")
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="PNG")
                zf.writestr("Metadata/thumbnail.png", img_bytes.getvalue())

            tmp_path = Path(tmp.name)

        try:
            success, thumbnail, error = ftp_browser_service.extract_3mf_thumbnail(
                tmp_path
            )

            assert success
            assert thumbnail is not None
            assert error is None

            # Verify it's a valid image
            img = Image.open(io.BytesIO(thumbnail))
            assert img.format == "PNG"
        finally:
            tmp_path.unlink()

    def test_extract_3mf_thumbnail_no_thumbnail(self, ftp_browser_service):
        """Test thumbnail extraction from 3MF file without thumbnail."""
        # Create a test 3MF file without thumbnail
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as tmp:
            with zipfile.ZipFile(tmp, "w") as zf:
                zf.writestr("3D/3dmodel.model", "<model/>")

            tmp_path = Path(tmp.name)

        try:
            success, thumbnail, error = ftp_browser_service.extract_3mf_thumbnail(
                tmp_path
            )

            assert not success
            assert thumbnail is None
            assert "No thumbnail found" in error
        finally:
            tmp_path.unlink()

    def test_extract_gcode_thumbnail(self, ftp_browser_service):
        """Test thumbnail extraction from G-code file."""
        # Create a test G-code file with embedded thumbnail
        thumbnail_data = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAA"
            "DUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
        gcode_content = f"""; Generated by Bambu Studio
; thumbnail begin 96x96 1234
; {thumbnail_data}
; thumbnail end
G28 ; Home all axes
M104 S200 ; Set extruder temp
"""

        with tempfile.NamedTemporaryFile(
            suffix=".gcode", delete=False, mode="w"
        ) as tmp:
            tmp.write(gcode_content)
            tmp_path = Path(tmp.name)

        try:
            success, thumbnail, error = ftp_browser_service.extract_gcode_thumbnail(
                tmp_path
            )

            assert success
            assert thumbnail is not None
            assert error is None
        finally:
            tmp_path.unlink()

    def test_extract_gcode_thumbnail_no_thumbnail(self, ftp_browser_service):
        """Test thumbnail extraction from G-code file without thumbnail."""
        gcode_content = """G28 ; Home all axes
M104 S200 ; Set extruder temp
G1 X10 Y10 F3000
"""

        with tempfile.NamedTemporaryFile(
            suffix=".gcode", delete=False, mode="w"
        ) as tmp:
            tmp.write(gcode_content)
            tmp_path = Path(tmp.name)

        try:
            success, thumbnail, error = ftp_browser_service.extract_gcode_thumbnail(
                tmp_path
            )

            assert not success
            assert thumbnail is None
            assert "No thumbnail found" in error
        finally:
            tmp_path.unlink()

    @patch("app.ftp_browser_service.CurlFTPSClient")
    def test_download_file_success(
        self, mock_curl_client, ftp_browser_service, printer_config, tmp_path
    ):
        """Test successful file download."""
        # Mock FTP client
        mock_client = Mock()
        mock_curl_client.return_value = mock_client

        def mock_download(remote_path, local_path, callback=None):
            # Create the file to simulate successful download
            Path(local_path).touch()
            return True, "Downloaded successfully"

        mock_client.download_file.side_effect = mock_download

        success, local_path, error = ftp_browser_service.download_file(
            printer_config, "/sdcard/test.3mf", "session123"
        )

        assert success
        assert local_path is not None
        assert error is None

    @patch("app.printer_service.PrinterService")
    def test_initiate_print_from_sd_success(
        self, mock_printer_service_class, ftp_browser_service, printer_config
    ):
        """Test successful print initiation from SD card."""
        # Mock printer service
        mock_printer_service = Mock()
        mock_printer_service_class.return_value = mock_printer_service

        mock_result = Mock()
        mock_result.success = True
        mock_result.message = "Print started"
        mock_printer_service.start_print.return_value = mock_result

        success, message = ftp_browser_service.initiate_print_from_sd(
            printer_config, "/sdcard/test.gcode"
        )

        assert success
        assert "Successfully started printing" in message
        mock_printer_service.start_print.assert_called_once_with(
            printer_config, "/sdcard/test.gcode"
        )

    @patch("app.printer_service.PrinterService")
    def test_initiate_print_from_sd_failure(
        self, mock_printer_service_class, ftp_browser_service, printer_config
    ):
        """Test failed print initiation from SD card."""
        # Mock printer service
        mock_printer_service = Mock()
        mock_printer_service_class.return_value = mock_printer_service

        mock_result = Mock()
        mock_result.success = False
        mock_result.message = "Printer busy"
        mock_printer_service.start_print.return_value = mock_result

        success, message = ftp_browser_service.initiate_print_from_sd(
            printer_config, "/sdcard/test.gcode"
        )

        assert not success
        assert message == "Printer busy"
