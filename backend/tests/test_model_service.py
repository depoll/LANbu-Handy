"""
Tests for Model Service - Model Download and Validation functionality.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import httpx

from app.model_service import (
    ModelService, 
    ModelValidationError, 
    ModelDownloadError
)


class TestModelService:
    """Test cases for the ModelService class."""
    
    def test_init_default(self):
        """Test ModelService initialization with defaults."""
        service = ModelService()
        assert service.max_file_size_bytes == 100 * 1024 * 1024  # 100MB
        assert service.temp_dir.name == "models"
        assert service.supported_extensions == {'.stl', '.3mf'}
    
    def test_init_custom_size(self):
        """Test ModelService initialization with custom size."""
        service = ModelService(max_file_size_mb=50)
        assert service.max_file_size_bytes == 50 * 1024 * 1024  # 50MB
    
    def test_validate_url_valid_http(self):
        """Test URL validation with valid HTTP URL."""
        service = ModelService()
        assert service.validate_url("http://example.com/model.stl") is True
    
    def test_validate_url_valid_https(self):
        """Test URL validation with valid HTTPS URL."""
        service = ModelService()
        assert service.validate_url("https://example.com/model.3mf") is True
    
    def test_validate_url_invalid_scheme(self):
        """Test URL validation with invalid scheme."""
        service = ModelService()
        assert service.validate_url("ftp://example.com/model.stl") is False
    
    def test_validate_url_no_scheme(self):
        """Test URL validation with no scheme."""
        service = ModelService()
        assert service.validate_url("example.com/model.stl") is False
    
    def test_validate_url_malformed(self):
        """Test URL validation with malformed URL."""
        service = ModelService()
        assert service.validate_url("not-a-url") is False
        assert service.validate_url("") is False
    
    def test_validate_file_extension_stl(self):
        """Test file extension validation for STL files."""
        service = ModelService()
        assert service.validate_file_extension("model.stl") is True
        assert service.validate_file_extension("model.STL") is True
    
    def test_validate_file_extension_3mf(self):
        """Test file extension validation for 3MF files."""
        service = ModelService()
        assert service.validate_file_extension("model.3mf") is True
        assert service.validate_file_extension("model.3MF") is True
    
    def test_validate_file_extension_invalid(self):
        """Test file extension validation for invalid extensions."""
        service = ModelService()
        assert service.validate_file_extension("model.obj") is False
        assert service.validate_file_extension("model.txt") is False
        assert service.validate_file_extension("model") is False
    
    def test_validate_file_size_valid(self):
        """Test file size validation with valid file."""
        service = ModelService()
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Write small amount of data
            temp_file.write(b"test data")
            temp_file.flush()
            temp_path = Path(temp_file.name)
        
        try:
            assert service.validate_file_size(temp_path) is True
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_validate_file_size_too_large(self):
        """Test file size validation with file too large."""
        service = ModelService(max_file_size_mb=1)  # 1MB limit
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Write more than 1MB of data
            temp_file.write(b"x" * (2 * 1024 * 1024))  # 2MB
            temp_file.flush()
            temp_path = Path(temp_file.name)
        
        try:
            assert service.validate_file_size(temp_path) is False
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_validate_file_size_nonexistent(self):
        """Test file size validation with non-existent file."""
        service = ModelService()
        non_existent_path = Path("/tmp/nonexistent_file.stl")
        assert service.validate_file_size(non_existent_path) is False
    
    def test_get_filename_from_url_with_filename(self):
        """Test filename extraction from URL with filename."""
        service = ModelService()
        url = "https://example.com/models/benchy.stl"
        filename = service.get_filename_from_url(url)
        assert filename == "benchy.stl"
    
    def test_get_filename_from_url_without_extension(self):
        """Test filename extraction from URL without extension."""
        service = ModelService()
        url = "https://example.com/models/benchy"
        filename = service.get_filename_from_url(url)
        assert filename == "benchy.stl"
    
    def test_get_filename_from_url_no_filename(self):
        """Test filename extraction from URL with no filename."""
        service = ModelService()
        url = "https://example.com/"
        filename = service.get_filename_from_url(url)
        assert filename == "model.stl"
    
    def test_get_filename_from_url_complex_path(self):
        """Test filename extraction from URL with complex path."""
        service = ModelService()
        url = "https://example.com/user/models/downloads/awesome_model.3mf"
        filename = service.get_filename_from_url(url)
        assert filename == "awesome_model.3mf"
    
    def test_cleanup_temp_file(self):
        """Test temporary file cleanup."""
        service = ModelService()
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(b"test data")
        
        # File should exist
        assert temp_path.exists()
        
        # Clean up
        service.cleanup_temp_file(temp_path)
        
        # File should be gone
        assert not temp_path.exists()
    
    def test_cleanup_temp_file_nonexistent(self):
        """Test cleanup of non-existent file (should not raise error)."""
        service = ModelService()
        non_existent_path = Path("/tmp/nonexistent_file.stl")
        
        # Should not raise an exception
        service.cleanup_temp_file(non_existent_path)
    
    def test_get_file_info(self):
        """Test getting file information."""
        service = ModelService()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".stl") as temp_file:
            temp_file.write(b"test data")
            temp_file.flush()
            temp_path = Path(temp_file.name)
        
        try:
            file_info = service.get_file_info(temp_path)
            
            assert file_info["filename"] == temp_path.name
            assert file_info["size_bytes"] == 9  # "test data" is 9 bytes
            assert file_info["extension"] == ".stl"
            assert file_info["path"] == str(temp_path)
            assert "size_mb" in file_info
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_get_file_info_nonexistent(self):
        """Test getting file info for non-existent file."""
        service = ModelService()
        non_existent_path = Path("/tmp/nonexistent_file.stl")
        
        file_info = service.get_file_info(non_existent_path)
        assert file_info == {}


class TestModelServiceDownload:
    """Test cases for model download functionality."""
    
    @pytest.mark.asyncio
    async def test_download_model_invalid_url(self):
        """Test download with invalid URL."""
        service = ModelService()
        
        with pytest.raises(ModelValidationError, match="Invalid URL format"):
            await service.download_model("not-a-url")
    
    @pytest.mark.asyncio
    async def test_download_model_invalid_extension(self):
        """Test download with invalid file extension."""
        service = ModelService()
        
        with pytest.raises(ModelValidationError, match="Unsupported file extension"):
            await service.download_model("https://example.com/model.obj")
    
    @pytest.mark.asyncio
    @patch('app.model_service.httpx.AsyncClient')
    async def test_download_model_http_error(self, mock_client_class):
        """Test download with HTTP error."""
        service = ModelService()
        
        # Mock HTTP client and response
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=Mock(), response=mock_response
        )
        
        # Set up the context manager properly
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.stream.return_value.__aenter__.return_value = mock_response
        mock_client.stream.return_value.__aexit__.return_value = None
        
        mock_client_class.return_value = mock_client
        
        with pytest.raises(ModelDownloadError, match="Failed to download file: HTTP 404"):
            await service.download_model("https://example.com/model.stl")
    
    @pytest.mark.asyncio
    @patch('app.model_service.httpx.AsyncClient')
    async def test_download_model_success(self, mock_client_class):
        """Test successful model download."""
        service = ModelService()
        
        # Mock HTTP client and response
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.headers = {}
        mock_response.raise_for_status = Mock()
        
        # Mock async iteration over chunks
        async def mock_aiter_bytes():
            yield b"test model data"
        
        mock_response.aiter_bytes.return_value = mock_aiter_bytes()
        
        # Set up the context managers properly
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.stream.return_value.__aenter__.return_value = mock_response
        mock_client.stream.return_value.__aexit__.return_value = None
        
        mock_client_class.return_value = mock_client
        
        # Download model
        file_path = await service.download_model("https://example.com/model.stl")
        
        try:
            # Verify file was created and contains data
            assert file_path.exists()
            assert file_path.suffix == ".stl"
            assert file_path.read_bytes() == b"test model data"
        finally:
            # Clean up
            service.cleanup_temp_file(file_path)
    
    @pytest.mark.asyncio
    @patch('app.model_service.httpx.AsyncClient')
    async def test_download_model_content_length_too_large(self, mock_client_class):
        """Test download with content-length exceeding limit."""
        service = ModelService(max_file_size_mb=1)  # 1MB limit
        
        # Mock HTTP client and response
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.headers = {'content-length': str(2 * 1024 * 1024)}  # 2MB
        mock_response.raise_for_status = Mock()
        
        # Set up the context managers properly
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.stream.return_value.__aenter__.return_value = mock_response
        mock_client.stream.return_value.__aexit__.return_value = None
        
        mock_client_class.return_value = mock_client
        
        with pytest.raises(ModelValidationError, match="File size exceeds maximum"):
            await service.download_model("https://example.com/model.stl")
    
    @pytest.mark.asyncio
    @patch('app.model_service.httpx.AsyncClient')
    async def test_download_model_actual_size_too_large(self, mock_client_class):
        """Test download where actual size exceeds limit during download."""
        service = ModelService(max_file_size_mb=1)  # 1MB limit
        
        # Mock HTTP client and response
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.headers = {}
        mock_response.raise_for_status = Mock()
        
        # Mock large data chunks
        async def mock_aiter_bytes():
            # Yield chunks that exceed the 1MB limit
            for _ in range(3):
                yield b"x" * (500 * 1024)  # 500KB chunks, total 1.5MB
        
        mock_response.aiter_bytes.return_value = mock_aiter_bytes()
        
        # Set up the context managers properly
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.stream.return_value.__aenter__.return_value = mock_response
        mock_client.stream.return_value.__aexit__.return_value = None
        
        mock_client_class.return_value = mock_client
        
        with pytest.raises(ModelValidationError, match="File size exceeds maximum"):
            await service.download_model("https://example.com/model.stl")