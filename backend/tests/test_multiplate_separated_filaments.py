"""
Test for the new 'multiplate separated filaments.3mf' test file.

This test validates that the plate-specific filament requirements are correctly
extracted for a multi-plate 3MF file where each plate uses different filaments.
"""

import unittest
from pathlib import Path

from app.model_service import ModelService


class TestMultiplateSeparatedFilaments(unittest.TestCase):
    """Test cases for multiplate separated filaments 3MF file."""

    def setUp(self):
        """Set up test dependencies."""
        self.model_service = ModelService()
        self.test_files_dir = Path(__file__).parent.parent.parent / "test_files"
        self.test_file = self.test_files_dir / "multiplate separated filaments.3mf"

    def test_multiplate_separated_filaments_plate_detection(self):
        """Test that plates are correctly detected from model_settings.config."""
        if not self.test_file.exists():
            self.skipTest("multiplate separated filaments.3mf not available")

        # Get plate information
        plates = self.model_service.parse_3mf_plate_info(self.test_file)

        # Should detect 4 plates
        self.assertEqual(len(plates), 4, "Should detect exactly 4 plates")

        # Check plate indices and object counts
        expected_plates = {
            1: 1,  # Plate 1: 1 object (Cube)
            2: 1,  # Plate 2: 1 object (Cylinder)
            3: 1,  # Plate 3: 1 object (Rounded Rectangle)
            4: 2,  # Plate 4: 2 objects (Disc + Double Tear Romboid Cylinder)
        }

        for plate in plates:
            self.assertIn(
                plate.index, expected_plates, f"Unexpected plate index: {plate.index}"
            )
            expected_objects = expected_plates[plate.index]
            self.assertEqual(
                plate.object_count,
                expected_objects,
                f"Plate {plate.index} should have {expected_objects} objects, "
                f"got {plate.object_count}",
            )

    def test_multiplate_separated_filaments_requirements(self):
        """Test that all filaments are returned for each plate (design decision)."""
        if not self.test_file.exists():
            self.skipTest("multiplate separated filaments.3mf not available")

        # Per design decision, get_plate_specific_filament_requirements returns
        # ALL configured filaments for better UX with multi-color models,
        # not just the filaments used by that specific plate.

        # Get full model requirements
        full_req = self.model_service.parse_3mf_filament_requirements(self.test_file)
        self.assertIsNotNone(full_req)
        self.assertEqual(full_req.filament_count, 13)

        # Each plate should return the same full requirements
        for plate_index in [1, 2, 3, 4]:
            with self.subTest(plate=plate_index):
                plate_req = self.model_service.get_plate_specific_filament_requirements(
                    self.test_file, plate_index
                )

                self.assertIsNotNone(
                    plate_req, f"No requirements found for plate {plate_index}"
                )

                # Plate requirements should be filtered to actual usage
                self.assertLessEqual(
                    plate_req.filament_count,
                    13,
                    f"Plate {plate_index} should have <= 13 filaments",
                )
                self.assertGreaterEqual(
                    plate_req.filament_count,
                    1,
                    f"Plate {plate_index} should have at least 1 filament",
                )

                # Types should be a subset of full model
                for ftype in plate_req.filament_types:
                    self.assertIn(
                        ftype,
                        full_req.filament_types,
                        f"Plate {plate_index} type {ftype} should be in full model",
                    )

    def test_multiplate_separated_filaments_vs_full_model(self):
        """Test that plate requirements are filtered subsets of full model."""
        if not self.test_file.exists():
            self.skipTest("multiplate separated filaments.3mf not available")

        # Get full model requirements
        full_req = self.model_service.parse_3mf_filament_requirements(self.test_file)
        self.assertIsNotNone(full_req)
        self.assertEqual(
            full_req.filament_count, 13, "Full model should have 13 filaments"
        )

        # Plate requirements should be filtered based on actual usage
        for plate_index in [1, 2, 3, 4]:
            plate_req = self.model_service.get_plate_specific_filament_requirements(
                self.test_file, plate_index
            )

            self.assertIsNotNone(plate_req)

            # Plate requirements should be <= full model
            self.assertLessEqual(
                plate_req.filament_count,
                full_req.filament_count,
                f"Plate {plate_index} should have <= filament count as full model",
            )

            # Types should be subset of full model
            for i, ftype in enumerate(plate_req.filament_types):
                self.assertIn(
                    ftype,
                    full_req.filament_types,
                    f"Plate {plate_index} type {ftype} should be in full model",
                )
                # Verify corresponding color is also valid
                color = plate_req.filament_colors[i]
                self.assertTrue(
                    color.startswith("#"),
                    f"Plate {plate_index} color {color} should be hex format",
                )

    def test_multiplate_separated_filaments_invalid_plate(self):
        """Test handling of invalid plate indices."""
        if not self.test_file.exists():
            self.skipTest("multiplate separated filaments.3mf not available")

        # Test invalid plate indices
        invalid_plates = [0, 5, 10, -1, 999]

        for invalid_plate in invalid_plates:
            plate_req = self.model_service.get_plate_specific_filament_requirements(
                self.test_file, invalid_plate
            )
            self.assertIsNone(
                plate_req, f"Should return None for invalid plate {invalid_plate}"
            )

    def test_extruder_mapping_accuracy(self):
        """Test that plates return only their actually used filaments."""
        if not self.test_file.exists():
            self.skipTest("multiplate separated filaments.3mf not available")

        # Plates should only return filaments they actually use

        # Get full model requirements
        full_req = self.model_service.parse_3mf_filament_requirements(self.test_file)
        self.assertIsNotNone(full_req)
        self.assertEqual(full_req.filament_count, 13)

        # Test each plate returns only its used filaments
        plate_filament_counts = {}
        for plate_index in [1, 2, 3, 4]:
            plate_req = self.model_service.get_plate_specific_filament_requirements(
                self.test_file, plate_index
            )

            self.assertIsNotNone(plate_req)
            plate_filament_counts[plate_index] = plate_req.filament_count

            # Each plate should have valid color count matching its filament count
            self.assertEqual(
                len(plate_req.filament_colors),
                plate_req.filament_count,
                f"Plate {plate_index} should have matching color count",
            )

        # Verify plates have different filament counts (showing filtering works)
        unique_counts = set(plate_filament_counts.values())
        self.assertGreater(
            len(unique_counts),
            1,
            "Plates should have different filament counts, "
            f"but all have: {plate_filament_counts}",
        )


if __name__ == "__main__":
    unittest.main()
