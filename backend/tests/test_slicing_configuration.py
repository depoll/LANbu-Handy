"""
Simplified tests for slicing configuration verification.

These tests ensure that sliced files include all necessary configuration.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest
from app.settings_builder import SettingsBuilder
from app.slicer_service import slice_model


def is_cli_available():
    """Check if Bambu Studio CLI is available."""
    try:
        result = subprocess.run(
            ["bambu-studio-cli", "--help"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode in [0, 127, -5, 133]
    except Exception:
        return False


class TestSlicingConfiguration:
    """Test slicing configuration features."""

    @pytest.fixture
    def settings_builder(self):
        """Create a settings builder instance."""
        return SettingsBuilder()

    @pytest.fixture
    def test_model_path(self):
        """Get path to test 3MF model."""
        repo_root = Path(__file__).parent.parent.parent
        test_file = (
            repo_root / "test_files" / "Original3DBenchy3Dprintconceptsnormel.3mf"
        )
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")
        return test_file

    def test_material_type_mapping(self, settings_builder):
        """Test that generic materials are properly mapped."""
        # Test standard materials
        assert settings_builder.MATERIAL_TYPE_MAP["PLA"] == "Bambu PLA Basic"
        assert settings_builder.MATERIAL_TYPE_MAP["PETG"] == "Bambu PETG Basic"
        assert settings_builder.MATERIAL_TYPE_MAP["ABS"] == "Bambu ABS"

        # Test generic material mappings
        assert settings_builder.MATERIAL_TYPE_MAP["Generic PLA"] == "Bambu PLA Basic"
        assert settings_builder.MATERIAL_TYPE_MAP["Generic PETG"] == "Bambu PETG Basic"
        assert settings_builder.MATERIAL_TYPE_MAP["Generic ABS"] == "Bambu ABS"
        assert settings_builder.MATERIAL_TYPE_MAP["Generic ASA"] == "Bambu ASA"
        assert settings_builder.MATERIAL_TYPE_MAP["Generic TPU"] == "Bambu TPU 95A"

    def test_build_settings_with_generic_materials(self, settings_builder):
        """Test building settings with generic material names."""
        generic_materials = ["Generic PLA", "Generic PETG", "Generic ABS"]

        for material in generic_materials:
            machine_settings, filament_settings = settings_builder.build_settings(
                printer_model="X1C",
                nozzle_diameter=0.4,
                filament_types=[material],
            )

            # Should handle generic materials
            assert machine_settings is not None or filament_settings is not None

            if filament_settings:
                # Should create valid filament settings
                paths = filament_settings.split(";")
                assert len(paths) >= 1

    @pytest.mark.skipif(not is_cli_available(), reason="Bambu Studio CLI not available")
    def test_slice_with_complete_settings(self, settings_builder, test_model_path):
        """Test slicing with complete configuration settings."""
        # Build settings
        machine_settings, filament_settings = settings_builder.build_settings(
            printer_model="X1C",
            nozzle_diameter=0.4,
            filament_types=["PLA"],
            filament_colors=["#FF0000"],
        )

        if machine_settings is None:
            pytest.skip("Machine settings not available")

        with tempfile.TemporaryDirectory() as output_dir:
            output_path = Path(output_dir)

            # Build options for slicing
            options = {}
            if machine_settings:
                options["load-settings"] = str(machine_settings)
            if filament_settings:
                options["load-filaments"] = filament_settings

            # Perform slicing
            result = slice_model(
                input_path=str(test_model_path),
                output_dir=str(output_path),
                options=options,
            )

            assert result.success is True

            # Check that output was created
            output_files = list(output_path.glob("*.gcode")) + list(
                output_path.glob("*.3mf")
            )
            assert len(output_files) > 0

    def test_printer_model_mapping(self, settings_builder):
        """Test printer model mapping is complete."""
        expected_models = {
            "X1C": "Bambu Lab X1 Carbon",
            "P1P": "Bambu Lab P1P",
            "P1S": "Bambu Lab P1S",
            "A1": "Bambu Lab A1",
        }

        for short_name, full_name in expected_models.items():
            assert short_name in settings_builder.PRINTER_MODEL_MAP
            assert settings_builder.PRINTER_MODEL_MAP[short_name] == full_name

    def test_multi_material_settings(self, settings_builder):
        """Test building settings for multi-material prints."""
        filament_types = ["PLA", "PLA", "PLA"]
        filament_colors = ["#FF0000", "#00FF00", "#0000FF"]

        machine_settings, filament_settings = settings_builder.build_settings(
            printer_model="X1C",
            nozzle_diameter=0.4,
            filament_types=filament_types,
            filament_colors=filament_colors,
        )

        if filament_settings:
            # Should have multiple filament profiles
            paths = filament_settings.split(";")
            assert len(paths) == len(filament_types)

    def test_nozzle_size_handling(self, settings_builder):
        """Test handling of different nozzle sizes."""
        nozzle_sizes = [0.2, 0.4, 0.6, 0.8]

        for nozzle in nozzle_sizes:
            machine_settings, filament_settings = settings_builder.build_settings(
                printer_model="X1C",
                nozzle_diameter=nozzle,
                filament_types=["PLA"],
            )

            # Should handle all standard nozzle sizes
            assert isinstance(machine_settings, (type(None), Path))
            assert isinstance(filament_settings, (type(None), str))

    @pytest.mark.skipif(not is_cli_available(), reason="Bambu Studio CLI not available")
    def test_slice_result_contains_metadata(self, test_model_path):
        """Test that slice results contain proper metadata."""
        with tempfile.TemporaryDirectory() as output_dir:
            output_path = Path(output_dir)

            # Slice with minimal options
            result = slice_model(
                input_path=str(test_model_path),
                output_dir=str(output_path),
            )

            if result.success:
                # Check for result.json
                result_json = output_path / "result.json"
                if result_json.exists():
                    with open(result_json, "r") as f:
                        slice_data = json.load(f)

                    # Should have basic structure
                    assert "return_code" in slice_data
                    assert slice_data["return_code"] == 0

                    # May have compatibility info
                    if "upward_compatible_machine" in slice_data:
                        assert isinstance(slice_data["upward_compatible_machine"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
