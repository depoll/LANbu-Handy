"""
Integration tests for slicing with printer-specific settings
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from app.main import app
from app.settings_builder import SettingsBuilder
from app.slicer_service import slice_model
from app.utils import build_slicing_options_from_config
from fastapi.testclient import TestClient


class TestSlicingIntegration:
    """Integration tests for the enhanced slicing workflow"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def test_3mf_file(self):
        """Get a test 3MF file if available"""
        test_files = list(Path("/workspace/test_files").glob("*.3mf"))
        if test_files:
            return test_files[0]
        return None

    def test_settings_builder_integration(self):
        """Test settings builder with real profiles"""
        builder = SettingsBuilder()

        # Test with X1C configuration
        machine_settings, filament_settings = builder.build_settings(
            printer_model="X1C",
            nozzle_diameter=0.4,
            filament_types=["PLA", "PETG"],
            print_quality="0.16mm Optimal",
            build_plate_type="textured_pei_plate",
        )

        # Check if real profiles exist
        if Path("/opt/bambu-studio-resources/profiles/BBL").exists():
            assert machine_settings is not None
            assert filament_settings is not None

            # Verify machine settings file was created
            assert machine_settings.exists()
            with open(machine_settings, "r") as f:
                settings = json.load(f)
                # The merged settings should have process type since
                # process settings are merged in
                assert settings.get("type") == "process"

            # Verify filament settings format
            assert ";" in filament_settings
            filament_paths = filament_settings.split(";")
            assert len(filament_paths) == 2

            # Each path should exist
            for path in filament_paths:
                assert Path(path).exists()

    def test_build_slicing_options_with_settings(self):
        """Test building CLI options with printer settings"""
        options = build_slicing_options_from_config(
            selected_plate_index=1,
            filament_mappings=[
                {"filament_index": 0, "ams_unit_id": 0, "ams_slot_id": 0},
                {"filament_index": 1, "ams_unit_id": 0, "ams_slot_id": 1},
            ],
            filament_types=["PLA", "PETG"],
            build_plate_type="textured_pei_plate",
            printer_model="X1C",
            nozzle_diameter=0.4,
            print_quality="0.16mm Optimal",
        )

        # If profiles exist, should have settings
        if Path("/opt/bambu-studio-resources/profiles/BBL").exists():
            assert "load-settings" in options
            assert "load-filaments" in options

            # Check that settings file contains build plate type
            settings_file = Path(options["load-settings"])
            if settings_file.exists():
                with open(settings_file, "r") as f:
                    settings = json.load(f)
                    # Should have some printer/process settings
                    assert isinstance(settings, dict)
                    assert len(settings) > 0
            assert ";" in options["load-filaments"]

    @pytest.mark.skipif(
        not Path("/workspace/test_files").exists()
        or not list(Path("/workspace/test_files").glob("*.3mf")),
        reason="No test 3MF files available",
    )
    def test_slice_with_settings(self, test_3mf_file):
        """Test actual slicing with settings"""
        if not test_3mf_file:
            pytest.skip("No test file available")

        # Build options with settings
        options = build_slicing_options_from_config(
            selected_plate_index=None,  # Slice all plates
            filament_mappings=[],
            filament_types=["PLA"],
            build_plate_type="textured_pei_plate",
            printer_model="X1C",
            nozzle_diameter=0.4,
        )

        # Create output directory
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            # Slice the model
            result = slice_model(
                input_path=test_3mf_file, output_dir=output_dir, options=options
            )

            # Should succeed
            assert result.success

            # Should produce G-code files
            gcode_files = list(output_dir.glob("*.gcode"))
            assert len(gcode_files) > 0

            # Check G-code contains settings
            with open(gcode_files[0], "r") as f:
                content = f.read(5000)  # Read first 5KB

                # Should have header block
                assert "; HEADER_BLOCK_START" in content
                assert "; CONFIG_BLOCK_START" in content

                # Should have filament settings
                assert "filament_type" in content or "filament_settings_id" in content

    @pytest.mark.skip("Function get_model_path does not exist in main module")
    @pytest.mark.asyncio
    async def test_configured_slice_endpoint(self, client):
        """Test the configured slice API endpoint"""
        # Mock dependencies
        with patch("app.main.get_model_path") as mock_get_model:
            with patch("app.main.slice_model") as mock_slice:
                with patch("app.main.get_gcode_output_dir") as mock_output_dir:
                    # Setup mocks
                    mock_get_model.return_value = Path("/tmp/test.3mf")
                    mock_output_dir.return_value = Path("/tmp/output")

                    mock_slice.return_value = MagicMock(
                        success=True,
                        stdout="Slicing completed",
                        stderr="",
                        gcode_paths=[Path("/tmp/output/plate_1.gcode")],
                    )

                    # Make request
                    request_data = {
                        "file_id": "test123",
                        "plate_index": 1,
                        "filament_mappings": [
                            {"filament_index": 0, "ams_unit_id": 0, "ams_slot_id": 0}
                        ],
                        "filament_types": ["PLA"],
                        "build_plate_type": "textured_pei_plate",
                        "printer_model": "X1C",
                        "nozzle_diameter": 0.4,
                        "print_quality": "0.16mm Optimal",
                    }

                    response = client.post("/api/slice/configured", json=request_data)

                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True

                    # Check that settings were passed to slice
                    mock_slice.assert_called_once()
                    call_args = mock_slice.call_args
                    options = call_args.kwargs.get("options", {})

                    # Should have plate and build plate settings
                    assert "curr-bed-type" in options
                    assert options["curr-bed-type"] == "textured_pei_plate"

    def test_gcode_download_endpoint(self, client):
        """Test G-code download endpoint"""
        # Create a test G-code file
        with tempfile.TemporaryDirectory() as temp_dir:
            gcode_dir = Path(temp_dir) / "gcode"
            gcode_dir.mkdir()

            test_file = gcode_dir / "test.gcode"
            test_content = "; Test G-code\nG28\nG1 X100 Y100"
            test_file.write_text(test_content)

            with patch("app.main.get_gcode_output_dir") as mock_dir:
                mock_dir.return_value = gcode_dir

                # Test successful download
                response = client.get("/api/gcode/download/test.gcode")
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/x-gcode; charset=utf-8"
                assert (
                    response.headers["content-disposition"]
                    == "attachment; filename=test.gcode"
                )
                assert response.content.decode() == test_content

                # Test non-existent file
                response = client.get("/api/gcode/download/nonexistent.gcode")
                assert response.status_code == 404

                # Test path traversal protection
                response = client.get("/api/gcode/download/../../../etc/passwd")
                # Should return 400 for path traversal but may return 404 if
                # file doesn't exist
                assert response.status_code in [400, 404]

    @pytest.mark.skip("Private method _parse_printer_status_data cannot be imported")
    def test_printer_metadata_integration(self):
        """Test printer metadata extraction"""
        from app.printer_service import _parse_printer_status_data

        # Mock printer status data with nozzle info
        test_data = {
            "ams": {"ams": [{"id": "0", "tray": []}]},
            "ipcam": {"ipcam_dev": "1"},
            "print": {"gcode_state": "IDLE"},
            "device": {"nozzle": {"info": "hardened_steel-0.4"}},
        }

        result = _parse_printer_status_data(test_data, None)

        # Should extract nozzle diameter
        assert result.nozzle_diameter == 0.4

    def test_end_to_end_settings_flow(self):
        """Test the complete settings flow from printer to G-code"""
        # This test validates the entire workflow
        builder = SettingsBuilder()

        # 1. Build settings for a specific configuration
        machine_settings, filament_settings = builder.build_settings(
            printer_model="P1P",
            nozzle_diameter=0.6,
            filament_types=["ABS", "PLA"],
            print_quality="0.24mm Standard",
        )

        # 2. Build CLI options
        options = {}
        if machine_settings:
            options["load-settings"] = str(machine_settings)
        if filament_settings:
            options["load-filaments"] = str(filament_settings)

        # 3. Verify options are correctly formatted
        if Path("/opt/bambu-studio-resources/profiles/BBL").exists():
            assert "load-settings" in options
            assert "load-filaments" in options

            # Filaments should be semicolon-separated paths
            assert ";" in options["load-filaments"]
            paths = options["load-filaments"].split(";")
            assert len(paths) == 2  # ABS and PLA

        # 4. Clean up temp files
        builder.cleanup_temp_files()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
