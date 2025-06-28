"""
Tests for 3MF metadata validation and extraction.

These tests verify that 3MF files contain all necessary configuration metadata
for successful printing, including printer settings, filament configuration,
and build plate information.
"""

import json
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest


class Test3MFMetadataValidation:
    """Test validation and extraction of metadata from 3MF files."""

    @pytest.fixture
    def create_test_3mf(self):
        """Create a test 3MF file with configurable metadata."""

        def _create_3mf(
            output_path: Path,
            printer_model: str = "Bambu Lab X1 Carbon",
            printer_settings_id: str = "Bambu Lab X1 Carbon 0.4 nozzle",
            nozzle_diameter: str = "0.4",
            filament_types: list = None,
            filament_colors: list = None,
            build_plate_type: str = "textured_plate",
            include_project_settings: bool = True,
        ):
            """Create a test 3MF file with specified metadata."""
            if filament_types is None:
                filament_types = ["PLA"]
            if filament_colors is None:
                filament_colors = ["#FF0000"]

            with zipfile.ZipFile(output_path, "w") as zf:
                # Create basic 3MF structure
                # 3D model file (minimal)
                model_xml = """<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US"
       xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
       xmlns:slic3rpe="http://schemas.slic3r.org/3mf/2017/06">
  <metadata name="printer_model">{}</metadata>
  <metadata name="printer_settings_id">{}</metadata>
  <metadata name="nozzle_diameter">{}</metadata>
  <resources>
    <object id="1" type="model">
      <mesh>
        <vertices>
          <vertex x="0" y="0" z="0"/>
          <vertex x="10" y="0" z="0"/>
          <vertex x="10" y="10" z="0"/>
          <vertex x="0" y="10" z="0"/>
        </vertices>
        <triangles>
          <triangle v1="0" v2="1" v3="2"/>
          <triangle v1="0" v2="2" v3="3"/>
        </triangles>
      </mesh>
    </object>
  </resources>
  <build>
    <item objectid="1"/>
  </build>
</model>""".format(
                    printer_model, printer_settings_id, nozzle_diameter
                )

                zf.writestr("3D/3dmodel.model", model_xml)

                # Create project settings config
                if include_project_settings:
                    project_settings = {
                        "printer_model": printer_model,
                        "printer_settings_id": printer_settings_id,
                        "nozzle_diameter": [nozzle_diameter],
                        "filament_type": filament_types,
                        "filament_colour": filament_colors,
                        "plate_name": build_plate_type,
                    }

                    # Create the config in the expected format
                    config_lines = []
                    for key, value in project_settings.items():
                        if isinstance(value, list):
                            value_str = json.dumps(value)
                        else:
                            value_str = str(value)
                        config_lines.append(f"{key} = {value_str}")

                    config_content = "\n".join(config_lines)
                    zf.writestr("Metadata/project_settings.config", config_content)

                # Add content types
                content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels"
           ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model"
           ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
  <Default Extension="config" ContentType="application/octet-stream"/>
</Types>"""
                zf.writestr("[Content_Types].xml", content_types)

        return _create_3mf

    def test_extract_printer_model_from_3mf(self, create_test_3mf):
        """Test extraction of printer model from 3MF metadata."""
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as tf:
            test_file = Path(tf.name)

        try:
            # Create test 3MF with X1 Carbon printer
            create_test_3mf(
                test_file,
                printer_model="Bambu Lab X1 Carbon",
                printer_settings_id="Bambu Lab X1 Carbon 0.4 nozzle",
            )

            # Extract metadata
            metadata = self._extract_3mf_metadata(test_file)

            # Verify printer model
            assert "printer_model" in metadata
            assert metadata["printer_model"] == "Bambu Lab X1 Carbon"

            # Verify printer settings ID
            assert "printer_settings_id" in metadata
            assert metadata["printer_settings_id"] == "Bambu Lab X1 Carbon 0.4 nozzle"

        finally:
            test_file.unlink(missing_ok=True)

    def test_extract_nozzle_diameter_from_3mf(self, create_test_3mf):
        """Test extraction of nozzle diameter from 3MF metadata."""
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as tf:
            test_file = Path(tf.name)

        try:
            # Test different nozzle sizes
            nozzle_sizes = ["0.2", "0.4", "0.6", "0.8"]

            for nozzle in nozzle_sizes:
                create_test_3mf(
                    test_file,
                    nozzle_diameter=nozzle,
                    printer_settings_id=f"Bambu Lab X1 Carbon {nozzle} nozzle",
                )

                metadata = self._extract_3mf_metadata(test_file)

                # Check both locations where nozzle might be stored
                if "nozzle_diameter" in metadata:
                    assert nozzle in str(metadata["nozzle_diameter"])
                elif "printer_settings_id" in metadata:
                    assert f"{nozzle} nozzle" in metadata["printer_settings_id"]
                else:
                    pytest.fail("No nozzle information found in metadata")

        finally:
            test_file.unlink(missing_ok=True)

    def test_extract_filament_configuration_from_3mf(self, create_test_3mf):
        """Test extraction of filament configuration from 3MF metadata."""
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as tf:
            test_file = Path(tf.name)

        try:
            # Multi-material configuration
            filament_types = ["PLA", "PETG", "ABS"]
            filament_colors = ["#FF0000", "#00FF00", "#0000FF"]

            create_test_3mf(
                test_file,
                filament_types=filament_types,
                filament_colors=filament_colors,
            )

            # Extract project settings
            metadata = self._extract_project_settings(test_file)

            # Verify filament types
            assert "filament_type" in metadata
            assert metadata["filament_type"] == filament_types

            # Verify filament colors
            assert "filament_colour" in metadata
            assert metadata["filament_colour"] == filament_colors

        finally:
            test_file.unlink(missing_ok=True)

    def test_extract_build_plate_type_from_3mf(self, create_test_3mf):
        """Test extraction of build plate type from 3MF metadata."""
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as tf:
            test_file = Path(tf.name)

        try:
            plate_types = ["cool_plate", "textured_plate", "engineering_plate"]

            for plate_type in plate_types:
                create_test_3mf(
                    test_file,
                    build_plate_type=plate_type,
                )

                metadata = self._extract_project_settings(test_file)

                # Verify build plate type
                assert "plate_name" in metadata
                assert metadata["plate_name"] == plate_type

        finally:
            test_file.unlink(missing_ok=True)

    def test_3mf_without_project_settings(self, create_test_3mf):
        """Test handling of 3MF files without project settings."""
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as tf:
            test_file = Path(tf.name)

        try:
            # Create 3MF without project settings
            create_test_3mf(
                test_file,
                include_project_settings=False,
            )

            # Should still extract basic metadata from model
            metadata = self._extract_3mf_metadata(test_file)

            # Basic metadata should still be present
            assert "printer_model" in metadata
            assert metadata["printer_model"] == "Bambu Lab X1 Carbon"

            # Project settings should be empty
            project_metadata = self._extract_project_settings(test_file)
            assert project_metadata == {}

        finally:
            test_file.unlink(missing_ok=True)

    def test_validate_complete_3mf_configuration(self, create_test_3mf):
        """Test validation of complete 3MF configuration."""
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as tf:
            test_file = Path(tf.name)

        try:
            # Create fully configured 3MF
            create_test_3mf(
                test_file,
                printer_model="Bambu Lab X1 Carbon",
                printer_settings_id="Bambu Lab X1 Carbon 0.4 nozzle",
                nozzle_diameter="0.4",
                filament_types=["PLA", "PETG"],
                filament_colors=["#FF0000", "#00FF00"],
                build_plate_type="textured_plate",
            )

            # Validate configuration completeness
            is_complete, missing = self._validate_3mf_completeness(test_file)

            assert is_complete is True
            assert len(missing) == 0

        finally:
            test_file.unlink(missing_ok=True)

    def test_validate_incomplete_3mf_configuration(self, create_test_3mf):
        """Test validation of incomplete 3MF configuration."""
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as tf:
            test_file = Path(tf.name)

        try:
            # Create 3MF without project settings (incomplete)
            create_test_3mf(
                test_file,
                include_project_settings=False,
            )

            # Validate configuration completeness
            is_complete, missing = self._validate_3mf_completeness(test_file)

            assert is_complete is False
            assert "filament_configuration" in missing
            assert "build_plate_type" in missing

        finally:
            test_file.unlink(missing_ok=True)

    def test_printer_compatibility_list_in_3mf(self, create_test_3mf):
        """Test that 3MF files can include printer compatibility information."""
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as tf:
            test_file = Path(tf.name)

        try:
            # Create 3MF for different printer models
            printer_configs = [
                ("X1C", "Bambu Lab X1 Carbon", "0.4"),
                ("P1P", "Bambu Lab P1P", "0.4"),
                ("A1", "Bambu Lab A1", "0.4"),
            ]

            for model_code, full_name, nozzle in printer_configs:
                create_test_3mf(
                    test_file,
                    printer_model=full_name,
                    printer_settings_id=f"{full_name} {nozzle} nozzle",
                    nozzle_diameter=nozzle,
                )

                metadata = self._extract_3mf_metadata(test_file)

                # Verify printer-specific metadata
                assert metadata["printer_model"] == full_name
                assert nozzle in metadata.get("nozzle_diameter", "")

        finally:
            test_file.unlink(missing_ok=True)

    def _extract_3mf_metadata(self, file_path: Path) -> dict:
        """Extract metadata from 3MF model file."""
        metadata = {}

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                # Check model file
                if "3D/3dmodel.model" in zf.namelist():
                    model_data = zf.read("3D/3dmodel.model")
                    root = ET.fromstring(model_data)

                    # Extract metadata elements
                    ns = {
                        "": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
                    }
                    for meta in root.findall(".//metadata", ns):
                        name = meta.get("name", "")
                        if name and meta.text:
                            metadata[name] = meta.text

                # Also check project settings
                if "Metadata/project_settings.config" in zf.namelist():
                    config_data = zf.read("Metadata/project_settings.config")
                    for line in config_data.decode("utf-8").split("\n"):
                        if " = " in line:
                            key, value = line.split(" = ", 1)
                            metadata[key.strip()] = value.strip()

        except Exception as e:
            pytest.fail(f"Failed to extract metadata: {e}")

        return metadata

    def _extract_project_settings(self, file_path: Path) -> dict:
        """Extract project settings from 3MF file."""
        settings = {}

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                if "Metadata/project_settings.config" in zf.namelist():
                    config_data = zf.read("Metadata/project_settings.config")
                    for line in config_data.decode("utf-8").split("\n"):
                        if " = " in line:
                            key, value = line.split(" = ", 1)
                            key = key.strip()
                            value = value.strip()

                            # Try to parse JSON arrays
                            if value.startswith("[") and value.endswith("]"):
                                try:
                                    settings[key] = json.loads(value)
                                except json.JSONDecodeError:
                                    settings[key] = value
                            else:
                                settings[key] = value

        except Exception as e:
            pytest.fail(f"Failed to extract project settings: {e}")

        return settings

    def _validate_3mf_completeness(self, file_path: Path) -> tuple[bool, list]:
        """Validate if 3MF file has all required configuration."""
        missing = []

        # Extract all metadata
        model_metadata = self._extract_3mf_metadata(file_path)
        project_settings = self._extract_project_settings(file_path)

        # Check required fields
        required_fields = {
            "printer_model": ["printer_model"],
            "nozzle_configuration": ["nozzle_diameter", "printer_settings_id"],
            "filament_configuration": ["filament_type", "filament_colour"],
            "build_plate_type": ["plate_name"],
        }

        for category, fields in required_fields.items():
            found = False
            for field in fields:
                if field in model_metadata or field in project_settings:
                    found = True
                    break
            if not found:
                missing.append(category)

        is_complete = len(missing) == 0
        return is_complete, missing

    def test_3mf_with_multiple_plates(self, create_test_3mf):
        """Test 3MF files with multiple build plates."""
        # This would require a more complex 3MF structure with plate information
        # For now, we'll test the concept
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as tf:
            test_file = Path(tf.name)

        try:
            # Create basic 3MF
            create_test_3mf(test_file)

            # In a real multi-plate 3MF, we'd have plate metadata
            # This is a placeholder for the test structure
            metadata = self._extract_3mf_metadata(test_file)

            # Verify basic structure exists
            assert metadata.get("printer_model") is not None

        finally:
            test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
