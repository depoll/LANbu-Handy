"""
Test suite for 3MF post-processing utilities.
"""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
from app.post_process_3mf import add_printer_model_id_to_3mf


def create_test_3mf(path: Path, printer_model_id: str = "") -> None:
    """Create a test 3MF file with slice_info.config."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Create a minimal 3MF structure
        zf.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?>')
        zf.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?>')

        # Create slice_info.config with printer_model_id
        slice_info_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<config>
    <plate>
        <metadata key="index" value="1"/>
        <metadata key="printer_model_id" value="{printer_model_id}"/>
        <metadata key="nozzle_diameters" value="0.4"/>
    </plate>
</config>"""
        zf.writestr("Metadata/slice_info.config", slice_info_content)


class TestPostProcess3MF:
    """Test 3MF post-processing functionality."""

    def test_add_printer_model_id_empty(self, tmp_path):
        """Test adding printer_model_id to a file where it's empty."""
        # Create test file with empty printer_model_id
        test_file = tmp_path / "test.3mf"
        create_test_3mf(test_file, printer_model_id="")

        # Add printer_model_id
        result = add_printer_model_id_to_3mf(test_file, "BL-P001")

        # Verify it was added
        with zipfile.ZipFile(result, "r") as zf:
            with zf.open("Metadata/slice_info.config") as f:
                tree = ET.parse(f)
                root = tree.getroot()

                for plate in root.findall(".//plate"):
                    for metadata in plate.findall("metadata"):
                        if metadata.get("key") == "printer_model_id":
                            assert metadata.get("value") == "BL-P001"
                            return

        pytest.fail("printer_model_id not found in output")

    def test_add_printer_model_id_already_set(self, tmp_path):
        """Test that existing printer_model_id is not overwritten."""
        # Create test file with existing printer_model_id
        test_file = tmp_path / "test.3mf"
        create_test_3mf(test_file, printer_model_id="BL-P002")

        # Try to add different printer_model_id
        result = add_printer_model_id_to_3mf(test_file, "BL-P001")

        # Verify it was NOT changed
        with zipfile.ZipFile(result, "r") as zf:
            with zf.open("Metadata/slice_info.config") as f:
                tree = ET.parse(f)
                root = tree.getroot()

                for plate in root.findall(".//plate"):
                    for metadata in plate.findall("metadata"):
                        if metadata.get("key") == "printer_model_id":
                            assert metadata.get("value") == "BL-P002"
                            return

        pytest.fail("printer_model_id not found in output")

    def test_add_printer_model_id_with_output_path(self, tmp_path):
        """Test adding printer_model_id with a different output path."""
        # Create test file
        test_file = tmp_path / "input.3mf"
        output_file = tmp_path / "output.3mf"
        create_test_3mf(test_file, printer_model_id="")

        # Add printer_model_id with output path
        result = add_printer_model_id_to_3mf(test_file, "BL-P001", output_file)

        # Verify paths
        assert result == output_file
        assert output_file.exists()
        assert test_file != output_file

        # Verify content
        with zipfile.ZipFile(output_file, "r") as zf:
            with zf.open("Metadata/slice_info.config") as f:
                tree = ET.parse(f)
                root = tree.getroot()

                for plate in root.findall(".//plate"):
                    for metadata in plate.findall("metadata"):
                        if metadata.get("key") == "printer_model_id":
                            assert metadata.get("value") == "BL-P001"
                            return

        pytest.fail("printer_model_id not found in output")

    def test_add_printer_model_id_missing_slice_info(self, tmp_path):
        """Test handling of 3MF file without slice_info.config."""
        # Create test file without slice_info.config
        test_file = tmp_path / "test.3mf"
        with zipfile.ZipFile(test_file, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?>')
            zf.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?>')

        # Try to add printer_model_id
        result = add_printer_model_id_to_3mf(test_file, "BL-P001")

        # Should succeed but not modify anything
        assert result == test_file
