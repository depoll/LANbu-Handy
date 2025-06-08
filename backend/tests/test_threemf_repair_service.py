"""
Tests for the ThreeMF repair service functionality.
"""

import zipfile
from pathlib import Path

import pytest
from app.threemf_repair_service import ThreeMFRepairError, ThreeMFRepairService


class TestThreeMFRepairService:
    """Test cases for the ThreeMF repair service."""

    @pytest.fixture
    def repair_service(self):
        """Create a repair service instance for testing."""
        return ThreeMFRepairService()

    @pytest.fixture
    def test_files_dir(self):
        """Get the test files directory."""
        return Path(__file__).parent.parent.parent / "test_files"

    def test_service_initialization(self, repair_service):
        """Test that the service initializes correctly."""
        assert (
            repair_service.default_namespace
            == "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
        )
        assert repair_service.temp_dir.exists()

    def test_needs_repair_non_3mf_file(self, repair_service, tmp_path):
        """Test that non-3MF files don't need repair."""
        stl_file = tmp_path / "test.stl"
        stl_file.write_text("solid test\nendsolid test")

        assert not repair_service.needs_repair(stl_file)

    def test_needs_repair_simple_3mf_file(self, repair_service, tmp_path):
        """Test detection of 3MF files that don't need repair."""
        # Create a simple 3MF file without external object references
        simple_3mf = tmp_path / "simple.3mf"

        with zipfile.ZipFile(simple_3mf, "w") as zf:
            zf.writestr(
                "3D/3dmodel.model",
                """<?xml version="1.0" encoding="UTF-8"?>
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

        assert not repair_service.needs_repair(simple_3mf)

    def test_needs_repair_bambu_3mf_file(self, repair_service, test_files_dir):
        """Test detection of Bambu Studio 3MF files that need repair."""
        bambu_file = test_files_dir / "Original3DBenchy3Dprintconceptsnormel.3mf"

        if bambu_file.exists():
            assert repair_service.needs_repair(bambu_file)
        else:
            pytest.skip("Test file not available")

    def test_repair_bambu_3mf_file(self, repair_service, test_files_dir):
        """Test repairing a real Bambu Studio 3MF file."""
        bambu_file = test_files_dir / "Original3DBenchy3Dprintconceptsnormel.3mf"

        if not bambu_file.exists():
            pytest.skip("Test file not available")

        repaired_file = repair_service.repair_3mf_file(bambu_file)

        assert repaired_file.exists()
        assert repaired_file.stat().st_size > 0

        # Verify the repaired file is a valid ZIP
        with zipfile.ZipFile(repaired_file, "r") as zf:
            assert "3D/3dmodel.model" in zf.namelist()

            # Check that the main model now has mesh data
            with zf.open("3D/3dmodel.model") as model_file:
                content = model_file.read().decode("utf-8")
                assert "mesh" in content.lower()
                assert "vertex" in content.lower()

    def test_repair_file_caching(self, repair_service, test_files_dir):
        """Test that repaired files are cached properly."""
        bambu_file = test_files_dir / "Original3DBenchy3Dprintconceptsnormel.3mf"

        if not bambu_file.exists():
            pytest.skip("Test file not available")

        # First repair
        repaired_file1 = repair_service.repair_3mf_file(bambu_file)
        modification_time1 = repaired_file1.stat().st_mtime

        # Second repair (should use cached version)
        repaired_file2 = repair_service.repair_3mf_file(bambu_file)
        modification_time2 = repaired_file2.stat().st_mtime

        assert repaired_file1 == repaired_file2
        assert modification_time1 == modification_time2

    def test_get_repaired_3mf_path(self, repair_service, tmp_path):
        """Test path generation for repaired files."""
        original_file = tmp_path / "test.3mf"
        original_file.touch()

        repaired_path = repair_service.get_repaired_3mf_path(original_file)

        assert repaired_path.name == "repaired_test.3mf"
        assert repaired_path.parent == repair_service.temp_dir

    def test_cleanup_old_repaired_files(self, repair_service):
        """Test cleanup of old repaired files."""
        # Create some test files in the repair temp directory
        old_file = repair_service.temp_dir / "repaired_old.3mf"
        old_file.touch()

        # Make the file appear old by modifying its timestamp
        import os
        import time

        old_time = time.time() - (25 * 3600)  # 25 hours ago
        os.utime(old_file, (old_time, old_time))

        # Create a newer file
        new_file = repair_service.temp_dir / "repaired_new.3mf"
        new_file.touch()

        # Run cleanup
        repair_service.cleanup_old_repaired_files(max_age_hours=24)

        # Old file should be removed, new file should remain
        assert not old_file.exists()
        assert new_file.exists()

        # Cleanup the new file
        new_file.unlink()

    def test_repair_invalid_file(self, repair_service, tmp_path):
        """Test repair error handling with invalid files."""
        invalid_file = tmp_path / "invalid.3mf"
        invalid_file.write_text("not a zip file")

        with pytest.raises(ThreeMFRepairError):
            repair_service.repair_3mf_file(invalid_file)

    def test_needs_repair_invalid_file(self, repair_service, tmp_path):
        """Test needs_repair with invalid files."""
        invalid_file = tmp_path / "invalid.3mf"
        invalid_file.write_text("not a zip file")

        # Should return False (not crash) for invalid files
        assert not repair_service.needs_repair(invalid_file)
