"""Tests for .3mf filament parsing functionality."""

import json
import tempfile
import zipfile
from pathlib import Path

import pytest

from app.model_service import ModelService, FilamentRequirement


class TestFilamentRequirement:
    """Test cases for the FilamentRequirement dataclass."""

    def test_filament_requirement_single_color(self):
        """Test single color filament requirement."""
        req = FilamentRequirement(
            filament_count=1,
            filament_types=["PLA"],
            filament_colors=["#FF0000"]
        )
        assert req.filament_count == 1
        assert req.filament_types == ["PLA"]
        assert req.filament_colors == ["#FF0000"]
        assert req.has_multicolor is False

    def test_filament_requirement_multicolor(self):
        """Test multicolor filament requirement."""
        req = FilamentRequirement(
            filament_count=3,
            filament_types=["PLA", "PETG", "ABS"],
            filament_colors=["#FF0000", "#00FF00", "#0000FF"]
        )
        assert req.filament_count == 3
        assert req.filament_types == ["PLA", "PETG", "ABS"]
        assert req.filament_colors == ["#FF0000", "#00FF00", "#0000FF"]
        assert req.has_multicolor is True

    def test_filament_requirement_post_init(self):
        """Test that has_multicolor is set correctly in __post_init__."""
        # Test with single filament (should set has_multicolor to False)
        req = FilamentRequirement(
            filament_count=1,
            filament_types=["PLA"],
            filament_colors=["#FF0000"],
            has_multicolor=True  # This should be overridden
        )
        assert req.has_multicolor is False

        # Test with multiple filaments (should set has_multicolor to True)
        req = FilamentRequirement(
            filament_count=2,
            filament_types=["PLA", "PETG"],
            filament_colors=["#FF0000", "#00FF00"],
            has_multicolor=False  # This should be overridden
        )
        assert req.has_multicolor is True


class TestParse3MFFilamentRequirements:
    """Test cases for parsing .3mf filament requirements."""

    def test_parse_3mf_non_3mf_file(self):
        """Test parsing non-.3mf file returns None."""
        service = ModelService()
        
        # Create a temporary STL file
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        try:
            result = service.parse_3mf_filament_requirements(temp_path)
            assert result is None
        finally:
            temp_path.unlink(missing_ok=True)

    def test_parse_3mf_corrupted_zip(self):
        """Test parsing corrupted .3mf file returns None."""
        service = ModelService()
        
        # Create a file with .3mf extension but invalid ZIP content
        with tempfile.NamedTemporaryFile(suffix='.3mf', delete=False) as temp_file:
            temp_file.write(b"Not a valid ZIP file")
            temp_path = Path(temp_file.name)
        
        try:
            result = service.parse_3mf_filament_requirements(temp_path)
            assert result is None
        finally:
            temp_path.unlink(missing_ok=True)

    def test_parse_3mf_missing_config(self):
        """Test parsing .3mf file without project_settings.config returns None."""
        service = ModelService()
        
        with tempfile.NamedTemporaryFile(suffix='.3mf', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        try:
            # Create a valid ZIP but without the config file
            with zipfile.ZipFile(temp_path, 'w') as zip_file:
                zip_file.writestr("some_other_file.txt", "content")
            
            result = service.parse_3mf_filament_requirements(temp_path)
            assert result is None
        finally:
            temp_path.unlink(missing_ok=True)

    def test_parse_3mf_invalid_json_config(self):
        """Test parsing .3mf file with invalid JSON config returns None."""
        service = ModelService()
        
        with tempfile.NamedTemporaryFile(suffix='.3mf', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        try:
            # Create a ZIP with invalid JSON in config
            with zipfile.ZipFile(temp_path, 'w') as zip_file:
                zip_file.writestr("Metadata/project_settings.config", "{ invalid json")
            
            result = service.parse_3mf_filament_requirements(temp_path)
            assert result is None
        finally:
            temp_path.unlink(missing_ok=True)

    def test_parse_3mf_valid_single_filament(self):
        """Test parsing .3mf file with single filament."""
        service = ModelService()
        
        config_data = {
            "filament_type": ["PLA"],
            "filament_colour": ["#FF0000"]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.3mf', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        try:
            with zipfile.ZipFile(temp_path, 'w') as zip_file:
                zip_file.writestr(
                    "Metadata/project_settings.config", 
                    json.dumps(config_data)
                )
            
            result = service.parse_3mf_filament_requirements(temp_path)
            assert result is not None
            assert result.filament_count == 1
            assert result.filament_types == ["PLA"]
            assert result.filament_colors == ["#FF0000"]
            assert result.has_multicolor is False
        finally:
            temp_path.unlink(missing_ok=True)

    def test_parse_3mf_valid_multicolor(self):
        """Test parsing .3mf file with multiple filaments."""
        service = ModelService()
        
        config_data = {
            "filament_type": ["PLA", "PETG", "ABS"],
            "filament_colour": ["#FF0000", "#00FF00", "#0000FF"]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.3mf', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        try:
            with zipfile.ZipFile(temp_path, 'w') as zip_file:
                zip_file.writestr(
                    "Metadata/project_settings.config", 
                    json.dumps(config_data)
                )
            
            result = service.parse_3mf_filament_requirements(temp_path)
            assert result is not None
            assert result.filament_count == 3
            assert result.filament_types == ["PLA", "PETG", "ABS"]
            assert result.filament_colors == ["#FF0000", "#00FF00", "#0000FF"]
            assert result.has_multicolor is True
        finally:
            temp_path.unlink(missing_ok=True)

    def test_parse_3mf_empty_types_default_to_pla(self):
        """Test parsing .3mf file with empty filament types defaults to PLA."""
        service = ModelService()
        
        config_data = {
            "filament_type": [],
            "filament_colour": ["#FF0000"]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.3mf', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        try:
            with zipfile.ZipFile(temp_path, 'w') as zip_file:
                zip_file.writestr(
                    "Metadata/project_settings.config", 
                    json.dumps(config_data)
                )
            
            result = service.parse_3mf_filament_requirements(temp_path)
            assert result is not None
            assert result.filament_count == 1
            assert result.filament_types == ["PLA"]  # Default
            assert result.filament_colors == ["#FF0000"]
        finally:
            temp_path.unlink(missing_ok=True)

    def test_parse_3mf_filters_empty_unknown_types(self):
        """Test parsing .3mf file filters out empty and unknown filament types."""
        service = ModelService()
        
        config_data = {
            "filament_type": ["PLA", "", "Unknown", "PETG", "  "],
            "filament_colour": ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF"]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.3mf', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        try:
            with zipfile.ZipFile(temp_path, 'w') as zip_file:
                zip_file.writestr(
                    "Metadata/project_settings.config", 
                    json.dumps(config_data)
                )
            
            result = service.parse_3mf_filament_requirements(temp_path)
            assert result is not None
            assert result.filament_count == 2  # Only PLA and PETG are valid
            assert result.filament_types == ["PLA", "PETG"]
            assert len(result.filament_colors) == 2
        finally:
            temp_path.unlink(missing_ok=True)

    def test_parse_3mf_pads_colors_to_match_types(self):
        """Test parsing .3mf file pads colors list to match types length."""
        service = ModelService()
        
        config_data = {
            "filament_type": ["PLA", "PETG", "ABS"],
            "filament_colour": ["#FF0000"]  # Only one color for 3 types
        }
        
        with tempfile.NamedTemporaryFile(suffix='.3mf', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        try:
            with zipfile.ZipFile(temp_path, 'w') as zip_file:
                zip_file.writestr(
                    "Metadata/project_settings.config", 
                    json.dumps(config_data)
                )
            
            result = service.parse_3mf_filament_requirements(temp_path)
            assert result is not None
            assert result.filament_count == 3
            assert result.filament_types == ["PLA", "PETG", "ABS"]
            assert len(result.filament_colors) == 3
            assert result.filament_colors[0] == "#FF0000"
            assert result.filament_colors[1] == "#000000"  # Default padding
            assert result.filament_colors[2] == "#000000"  # Default padding
        finally:
            temp_path.unlink(missing_ok=True)

    def test_parse_3mf_real_files(self):
        """Test parsing real .3mf files from test_files directory."""
        service = ModelService()
        
        # Test multicolor coin file
        multicolor_file = Path("/home/runner/work/LANbu-Handy/LANbu-Handy/test_files/multicolor-test-coin.3mf")
        if multicolor_file.exists():
            result = service.parse_3mf_filament_requirements(multicolor_file)
            assert result is not None
            assert result.filament_count > 1
            assert result.has_multicolor is True
            assert "PLA" in result.filament_types  # Should contain PLA
        
        # Test single color benchy file
        benchy_file = Path("/home/runner/work/LANbu-Handy/LANbu-Handy/test_files/Original3DBenchy3Dprintconceptsnormel.3mf")
        if benchy_file.exists():
            result = service.parse_3mf_filament_requirements(benchy_file)
            assert result is not None
            # This one should be single color
            if result.filament_count == 1:
                assert result.has_multicolor is False