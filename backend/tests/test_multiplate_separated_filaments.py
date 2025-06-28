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

                # Should return all 13 filaments regardless of plate
                self.assertEqual(
                    plate_req.filament_count,
                    13,
                    f"Plate {plate_index} should return all 13 filaments",
                )

                # Should match full model requirements
                self.assertEqual(
                    plate_req.filament_types,
                    full_req.filament_types,
                    f"Plate {plate_index} should have same types as full model",
                )

                self.assertEqual(
                    plate_req.filament_colors,
                    full_req.filament_colors,
                    f"Plate {plate_index} should have same colors as full model",
                )

    def test_multiplate_separated_filaments_vs_full_model(self):
        """Test that plate requirements match full model (design decision)."""
        if not self.test_file.exists():
            self.skipTest("multiplate separated filaments.3mf not available")

        # Get full model requirements
        full_req = self.model_service.parse_3mf_filament_requirements(self.test_file)
        self.assertIsNotNone(full_req)
        self.assertEqual(
            full_req.filament_count, 13, "Full model should have 13 filaments"
        )

        # Per design decision, plate requirements should match full model
        for plate_index in [1, 2, 3, 4]:
            plate_req = self.model_service.get_plate_specific_filament_requirements(
                self.test_file, plate_index
            )

            self.assertIsNotNone(plate_req)

            # Plate requirements should equal full model
            self.assertEqual(
                plate_req.filament_count,
                full_req.filament_count,
                f"Plate {plate_index} should have same filament count as full model",
            )

            # Should match full model exactly
            self.assertEqual(
                plate_req.filament_types,
                full_req.filament_types,
                f"Plate {plate_index} should have same types as full model",
            )
            self.assertEqual(
                plate_req.filament_colors,
                full_req.filament_colors,
                f"Plate {plate_index} should have same colors as full model",
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
        """Test that all filaments are returned regardless of plate."""
        if not self.test_file.exists():
            self.skipTest("multiplate separated filaments.3mf not available")

        # Per design decision, all plates return all configured filaments
        # to support proper AMS mapping for multi-color models

        # Get full model requirements
        full_req = self.model_service.parse_3mf_filament_requirements(self.test_file)
        self.assertIsNotNone(full_req)
        self.assertEqual(full_req.filament_count, 13)

        # Test all plates return same requirements
        for plate_index in [1, 2, 3, 4]:
            plate_req = self.model_service.get_plate_specific_filament_requirements(
                self.test_file, plate_index
            )

            self.assertIsNotNone(plate_req)
            self.assertEqual(plate_req.filament_count, 13)

            # All plates should have same 13 colors as full model
            self.assertEqual(
                len(plate_req.filament_colors),
                13,
                f"Plate {plate_index} should have all 13 colors",
            )
            self.assertEqual(
                plate_req.filament_colors,
                full_req.filament_colors,
                f"Plate {plate_index} colors should match full model",
            )


if __name__ == "__main__":
    unittest.main()
