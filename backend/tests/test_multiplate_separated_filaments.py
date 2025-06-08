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
        """Test plate-specific filament requirements extraction."""
        if not self.test_file.exists():
            self.skipTest("multiplate separated filaments.3mf not available")

        # Expected filament configuration per plate based on the test file
        expected_requirements = {
            1: {  # Object 2 uses extruder 1
                "count": 1,
                "types": ["PLA"],
                "colors": ["#996633"],  # Brown
            },
            2: {  # Object 4 uses extruder 4
                "count": 1,
                "types": ["PLA"],
                "colors": ["#0000FF"],  # Blue
            },
            3: {  # Object 6 uses extruder 12
                "count": 1,
                "types": ["PLA"],
                "colors": ["#515151"],  # Dark Gray
            },
            4: {  # Objects 8,10 use extruders 8,5
                "count": 2,
                "types": ["PLA", "PLA"],
                "colors": [
                    "#21FF06",
                    "#800080",
                ],  # Green, Purple (sorted by extruder ID)
            },
        }

        for plate_index, expected in expected_requirements.items():
            with self.subTest(plate=plate_index):
                plate_req = self.model_service.get_plate_specific_filament_requirements(
                    self.test_file, plate_index
                )

                self.assertIsNotNone(
                    plate_req, f"No requirements found for plate {plate_index}"
                )

                # Check filament count
                self.assertEqual(
                    plate_req.filament_count,
                    expected["count"],
                    f"Plate {plate_index} should require {expected['count']} filaments",
                )

                # Check filament types
                self.assertEqual(
                    plate_req.filament_types,
                    expected["types"],
                    f"Plate {plate_index} should have types {expected['types']}",
                )

                # Check filament colors
                self.assertEqual(
                    plate_req.filament_colors,
                    expected["colors"],
                    f"Plate {plate_index} should have colors {expected['colors']}",
                )

    def test_multiplate_separated_filaments_vs_full_model(self):
        """Test that plate requirements are properly filtered from full model."""
        if not self.test_file.exists():
            self.skipTest("multiplate separated filaments.3mf not available")

        # Get full model requirements
        full_req = self.model_service.parse_3mf_filament_requirements(self.test_file)
        self.assertIsNotNone(full_req)
        self.assertEqual(
            full_req.filament_count, 13, "Full model should have 13 filaments"
        )

        # Test each plate shows significant reduction
        for plate_index in [1, 2, 3, 4]:
            plate_req = self.model_service.get_plate_specific_filament_requirements(
                self.test_file, plate_index
            )

            self.assertIsNotNone(plate_req)

            # Plate requirements should be much less than full model
            self.assertLess(
                plate_req.filament_count,
                full_req.filament_count,
                f"Plate {plate_index} should require fewer filaments than full model",
            )

            # Should require at most 2 filaments (plate 4 has 2, others have 1)
            self.assertLessEqual(
                plate_req.filament_count,
                2,
                f"Plate {plate_index} should require at most 2 filaments",
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
        """Test that extruder to filament mapping is accurate."""
        if not self.test_file.exists():
            self.skipTest("multiplate separated filaments.3mf not available")

        # Mapping from plate to expected extruder IDs (based on objects in that plate)
        expected_extruders = {
            1: [1],  # Object 2 uses extruder 1
            2: [4],  # Object 4 uses extruder 4
            3: [12],  # Object 6 uses extruder 12
            4: [5, 8],  # Objects 10,8 use extruders 5,8 (sorted order)
        }

        # Expected colors by extruder ID (1-based indexing)
        extruder_colors = {
            1: "#996633",  # Extruder 1 -> filament_colour[0]
            4: "#0000FF",  # Extruder 4 -> filament_colour[3]
            5: "#21FF06",  # Extruder 5 -> filament_colour[4]
            8: "#800080",  # Extruder 8 -> filament_colour[7]
            12: "#515151",  # Extruder 12 -> filament_colour[11]
        }

        for plate_index, expected_extruder_ids in expected_extruders.items():
            plate_req = self.model_service.get_plate_specific_filament_requirements(
                self.test_file, plate_index
            )

            self.assertIsNotNone(plate_req)
            self.assertEqual(len(plate_req.filament_colors), len(expected_extruder_ids))

            # Verify colors match expected extruders (in sorted order)
            expected_colors = [
                extruder_colors[ext_id] for ext_id in sorted(expected_extruder_ids)
            ]
            self.assertEqual(
                plate_req.filament_colors,
                expected_colors,
                f"Plate {plate_index} colors don't match expected extruder mapping",
            )


if __name__ == "__main__":
    unittest.main()
