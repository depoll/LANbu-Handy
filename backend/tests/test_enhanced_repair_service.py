"""Tests for the enhanced 3MF repair service."""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
from app.threemf_repair_service_enhanced import EnhancedThreeMFRepairService


class TestEnhancedThreeMFRepairService:
    """Test cases for the enhanced 3MF repair service."""

    @pytest.fixture
    def repair_service(self):
        """Create a repair service instance."""
        return EnhancedThreeMFRepairService()

    @pytest.fixture
    def test_files_dir(self):
        """Get the test files directory."""
        return Path(__file__).parent.parent.parent / "test_files"

    def test_needs_repair_detection(self, repair_service, test_files_dir):
        """Test detection of 3MF files that need repair."""
        # Test with Bambu 3MF file
        bambu_file = test_files_dir / "Original3DBenchy3Dprintconceptsnormel.3mf"
        assert repair_service.needs_repair(bambu_file) is True

        # Test with STL file (should not need repair)
        stl_file = test_files_dir / "Dice Tower.stl"
        assert repair_service.needs_repair(stl_file) is False

    def test_repair_bambu_3mf(self, repair_service, test_files_dir):
        """Test repairing a Bambu Studio 3MF file."""
        input_file = test_files_dir / "Original3DBenchy3Dprintconceptsnormel.3mf"

        # Repair the file
        output_file = repair_service.repair_3mf_file(input_file)

        # Verify output exists
        assert output_file.exists()
        assert output_file.suffix == ".3mf"

        # Verify it's a valid zip file
        assert zipfile.is_zipfile(output_file)

        # Check the repaired file structure
        with zipfile.ZipFile(output_file, "r") as zf:
            # Should have required files
            assert "[Content_Types].xml" in zf.namelist()
            assert "_rels/.rels" in zf.namelist()
            assert "3D/3dmodel.model" in zf.namelist()
            assert "3D/_rels/3dmodel.model.rels" in zf.namelist()

            # Should NOT have external object files
            object_files = [
                f
                for f in zf.namelist()
                if f.startswith("3D/Objects/") and f.endswith(".model")
            ]
            assert len(object_files) == 0

            # Check the main model content
            with zf.open("3D/3dmodel.model") as model_file:
                content = model_file.read().decode("utf-8")
                root = ET.fromstring(content)

                # Should have exactly one object
                objects = root.findall(
                    ".//{http://schemas.microsoft.com/3dmanufacturing/"
                    "core/2015/02}object"
                )
                assert len(objects) == 1

                # Should have mesh data
                meshes = root.findall(
                    ".//{http://schemas.microsoft.com/3dmanufacturing/"
                    "core/2015/02}mesh"
                )
                assert len(meshes) == 1

                # Should have vertices and triangles
                vertices = root.findall(
                    ".//{http://schemas.microsoft.com/3dmanufacturing/"
                    "core/2015/02}vertex"
                )
                triangles = root.findall(
                    ".//{http://schemas.microsoft.com/3dmanufacturing/"
                    "core/2015/02}triangle"
                )

                assert len(vertices) > 0
                assert len(triangles) > 0

                # Should not have component references
                components = root.findall(
                    ".//{http://schemas.microsoft.com/3dmanufacturing/"
                    "core/2015/02}component"
                )
                assert len(components) == 0

    def test_repair_multicolor_3mf(self, repair_service, test_files_dir):
        """Test repairing a multicolor 3MF file."""
        input_file = test_files_dir / "multicolor-test-coin.3mf"

        if not input_file.exists():
            pytest.skip("Multicolor test file not found")

        # Repair the file
        output_file = repair_service.repair_3mf_file(input_file)

        # Verify output exists and is valid
        assert output_file.exists()
        assert zipfile.is_zipfile(output_file)

    def test_repair_already_simple_3mf(self, repair_service, tmp_path):
        """Test that simple 3MF files are handled correctly."""
        # Create a simple 3MF that doesn't need repair
        simple_3mf = tmp_path / "simple.3mf"

        with zipfile.ZipFile(simple_3mf, "w") as zf:
            # Minimal content
            zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
            zf.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships/>')
            zf.writestr(
                "3D/3dmodel.model",
                """<?xml version="1.0"?>
<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
    <resources>
        <object id="1" type="model">
            <mesh>
                <vertices>
                    <vertex x="0" y="0" z="0"/>
                    <vertex x="1" y="0" z="0"/>
                    <vertex x="0" y="1" z="0"/>
                </vertices>
                <triangles>
                    <triangle v1="0" v2="1" v3="2"/>
                </triangles>
            </mesh>
        </object>
    </resources>
    <build>
        <item objectid="1"/>
    </build>
</model>""",
            )

        # Should not need repair
        assert repair_service.needs_repair(simple_3mf) is False

        # But repair should still work
        output_file = repair_service.repair_3mf_file(simple_3mf)
        assert output_file.exists()

    def test_cleanup_old_files(self, repair_service, tmp_path, monkeypatch):
        """Test cleanup of old repaired files."""
        # Temporarily change repair service temp dir
        monkeypatch.setattr(repair_service, "temp_dir", tmp_path)

        # Create some test files
        import time

        current_time = time.time()

        # Old file (should be deleted)
        old_file = tmp_path / "repaired_old.3mf"
        old_file.write_text("old")
        # Set modification time to 25 hours ago
        import os

        os.utime(old_file, (current_time - 90000, current_time - 90000))

        # Recent file (should be kept)
        recent_file = tmp_path / "repaired_recent.3mf"
        recent_file.write_text("recent")

        # Run cleanup
        repair_service.cleanup_old_repaired_files(max_age_hours=24)

        # Check results
        assert not old_file.exists()
        assert recent_file.exists()
