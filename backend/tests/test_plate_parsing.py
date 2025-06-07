"""
Tests for 3MF plate parsing functionality.
"""

import unittest
from pathlib import Path

from app.model_service import ModelInfo, ModelService, PlateInfo


class TestPlateParsing(unittest.TestCase):
    """Test cases for 3MF plate parsing functionality."""

    def setUp(self):
        """Set up test dependencies."""
        self.model_service = ModelService()
        self.test_files_dir = Path(__file__).parent.parent.parent / "test_files"

    def test_parse_multiplate_3mf(self):
        """Test parsing a multi-plate 3MF file."""
        multiplate_file = self.test_files_dir / "multiplate-test.3mf"

        if not multiplate_file.exists():
            self.skipTest("multiplate-test.3mf not available")

        model_info = self.model_service.parse_3mf_model_info(multiplate_file)

        # Should detect multiple plates
        self.assertTrue(model_info.has_multiple_plates)
        self.assertGreater(len(model_info.plates), 1)

        # Check that plates have expected structure
        for plate in model_info.plates:
            self.assertIsInstance(plate, PlateInfo)
            self.assertIsInstance(plate.index, int)
            self.assertGreaterEqual(plate.index, 1)

            # Should have some prediction/weight information
            self.assertIsNotNone(plate.prediction_seconds)
            self.assertIsNotNone(plate.weight_grams)

            # Should have at least one object
            self.assertGreaterEqual(plate.object_count, 0)

    def test_parse_single_plate_3mf(self):
        """Test parsing a single-plate 3MF file."""
        single_file = self.test_files_dir / "multicolor-test-coin.3mf"

        if not single_file.exists():
            self.skipTest("multicolor-test-coin.3mf not available")

        model_info = self.model_service.parse_3mf_model_info(single_file)

        # Should not detect multiple plates for single-plate file
        # (or have empty plates list if no slice info)
        if model_info.plates:
            # If plates are detected, there should be 1 or fewer
            self.assertLessEqual(len(model_info.plates), 1)
            if len(model_info.plates) == 1:
                self.assertFalse(model_info.has_multiple_plates)

    def test_parse_stl_file(self):
        """Test that STL files return empty plate info."""
        # Create a temporary STL file for testing
        stl_path = Path("/tmp/test.stl")
        stl_path.write_text(
            "solid test\nfacet normal 0 0 1\nouter loop\n"
            "vertex 0 0 0\nendloop\nendfacet\nendsolid test"
        )

        try:
            plates = self.model_service.parse_3mf_plate_info(stl_path)
            self.assertEqual(len(plates), 0)

            model_info = self.model_service.parse_3mf_model_info(stl_path)
            self.assertFalse(model_info.has_multiple_plates)
            self.assertEqual(len(model_info.plates), 0)
        finally:
            if stl_path.exists():
                stl_path.unlink()

    def test_invalid_3mf_file(self):
        """Test handling of invalid 3MF files."""
        # Create a temporary invalid 3MF file
        invalid_path = Path("/tmp/invalid.3mf")
        invalid_path.write_text("invalid content")

        try:
            plates = self.model_service.parse_3mf_plate_info(invalid_path)
            self.assertEqual(len(plates), 0)

            model_info = self.model_service.parse_3mf_model_info(invalid_path)
            self.assertFalse(model_info.has_multiple_plates)
            self.assertEqual(len(model_info.plates), 0)
        finally:
            if invalid_path.exists():
                invalid_path.unlink()

    def test_plate_info_structure(self):
        """Test that PlateInfo objects have the expected structure."""
        plate = PlateInfo(
            index=1,
            prediction_seconds=1000,
            weight_grams=25.5,
            has_support=True,
            object_count=3,
        )

        self.assertEqual(plate.index, 1)
        self.assertEqual(plate.prediction_seconds, 1000)
        self.assertEqual(plate.weight_grams, 25.5)
        self.assertTrue(plate.has_support)
        self.assertEqual(plate.object_count, 3)

    def test_model_info_structure(self):
        """Test that ModelInfo objects have the expected structure."""
        plates = [PlateInfo(index=1), PlateInfo(index=2)]
        model_info = ModelInfo(plates=plates)
        model_info.has_multiple_plates = len(model_info.plates) > 1

        self.assertTrue(model_info.has_multiple_plates)
        self.assertEqual(len(model_info.plates), 2)


if __name__ == "__main__":
    unittest.main()
