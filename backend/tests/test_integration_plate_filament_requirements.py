"""
Integration test for plate-specific filament requirements functionality.
"""

import unittest
from pathlib import Path

from app.model_service import ModelService


class TestPlateSpecificFilamentRequirementsIntegration(unittest.TestCase):
    """Integration test for plate-specific filament requirements."""

    def setUp(self):
        """Set up test dependencies."""
        self.model_service = ModelService()
        self.test_files_dir = Path(__file__).parent.parent.parent / "test_files"

    def test_multiplate_filament_requirements_filtering(self):
        """Test that plate-specific requirements are properly filtered."""
        multiplate_file = self.test_files_dir / "multiplate separated filaments.3mf"

        if not multiplate_file.exists():
            self.skipTest("multiplate separated filaments.3mf not available")

        # Get full model requirements
        full_requirements = self.model_service.parse_3mf_filament_requirements(
            multiplate_file
        )
        self.assertIsNotNone(full_requirements)
        self.assertGreater(full_requirements.filament_count, 1)
        self.assertEqual(full_requirements.filament_count, 13)  # Should have 13 total

        # Get plate information
        plates = self.model_service.parse_3mf_plate_info(multiplate_file)
        self.assertGreater(len(plates), 1)
        self.assertEqual(len(plates), 4)  # Should have 4 plates

        # Expected filament counts per plate (based on our test file)
        expected_filament_counts = {
            1: 1,  # Plate 1: 1 filament
            2: 1,  # Plate 2: 1 filament
            3: 1,  # Plate 3: 1 filament
            4: 2,  # Plate 4: 2 filaments
        }

        # Test plate-specific requirements for each plate
        for plate in plates:
            plate_requirements = (
                self.model_service.get_plate_specific_filament_requirements(
                    multiplate_file, plate.index
                )
            )

            # Should return valid requirements
            self.assertIsNotNone(plate_requirements)

            # Plate requirements should be equal or less than full requirements
            self.assertLessEqual(
                plate_requirements.filament_count, full_requirements.filament_count
            )

            # Should have at least 1 filament
            self.assertGreaterEqual(plate_requirements.filament_count, 1)

            # Check expected filament count for this plate
            expected_count = expected_filament_counts.get(plate.index)
            if expected_count:
                self.assertEqual(
                    plate_requirements.filament_count,
                    expected_count,
                    f"Plate {plate.index} should have {expected_count} filaments",
                )

            # Filament types should be a subset of full model types
            for plate_type in plate_requirements.filament_types:
                self.assertIn(
                    plate_type,
                    full_requirements.filament_types,
                    f"Plate {plate.index} type {plate_type} not in full model types",
                )

            print(
                f"Plate {plate.index}: {plate_requirements.filament_count} filaments "
                f"(reduced from {full_requirements.filament_count})"
            )

    def test_specific_filament_types_per_plate(self):
        """Test that specific filament types are correctly extracted per plate."""
        multiplate_file = self.test_files_dir / "multiplate separated filaments.3mf"

        if not multiplate_file.exists():
            self.skipTest("multiplate separated filaments.3mf not available")

        # Expected filament types per plate based on our test file design
        expected_plate_filaments = {
            1: ["PLA"],  # Single filament
            2: ["PLA"],  # Single filament
            3: ["PLA"],  # Single filament
            4: ["PLA", "PLA"],  # Two filaments
        }

        expected_plate_colors = {
            1: ["#996633"],  # Brown
            2: ["#0000FF"],  # Blue
            3: ["#515151"],  # Gray
            4: ["#21FF06", "#800080"],  # Green + Purple
        }

        for plate_index, expected_types in expected_plate_filaments.items():
            plate_requirements = (
                self.model_service.get_plate_specific_filament_requirements(
                    multiplate_file, plate_index
                )
            )

            self.assertIsNotNone(plate_requirements)
            self.assertEqual(
                plate_requirements.filament_types,
                expected_types,
                f"Plate {plate_index} should have filament types: {expected_types}",
            )
            self.assertEqual(
                plate_requirements.filament_colors,
                expected_plate_colors[plate_index],
                f"Plate {plate_index} should have colors: "
                f"{expected_plate_colors[plate_index]}",
            )

        print("Specific filament types per plate validated successfully")

    def test_original_multiplate_file_behavior(self):
        """Test original multiplate-test.3mf with correct requirements per plate."""
        multiplate_file = self.test_files_dir / "multiplate-test.3mf"

        if not multiplate_file.exists():
            self.skipTest("multiplate-test.3mf not available")

        # Get full model requirements
        full_requirements = self.model_service.parse_3mf_filament_requirements(
            multiplate_file
        )
        self.assertIsNotNone(full_requirements)
        self.assertEqual(full_requirements.filament_count, 4)

        # Get plate information
        plates = self.model_service.parse_3mf_plate_info(multiplate_file)
        self.assertEqual(len(plates), 7)  # Should have 7 plates

        # All plates in this test file use all 4 filaments (actual data)
        for plate in plates:
            plate_requirements = (
                self.model_service.get_plate_specific_filament_requirements(
                    multiplate_file, plate.index
                )
            )

            self.assertIsNotNone(plate_requirements)

            # All plates use all 4 filaments in this specific test file
            # This is because each object has parts using extruders 1,2,3,4
            self.assertEqual(
                plate_requirements.filament_count,
                4,
                f"Plate {plate.index} should use all 4 filaments in this test file",
            )
            self.assertEqual(
                plate_requirements.filament_types, ["PLA", "PLA", "PLA", "PLA"]
            )

        print(
            "Original multiplate-test.3mf: All plates use all 4 filaments "
            "(each object has parts using extruders 1,2,3,4)"
        )

    def test_invalid_plate_index_handling(self):
        """Test handling of invalid plate indices."""
        multiplate_file = self.test_files_dir / "multiplate separated filaments.3mf"

        if not multiplate_file.exists():
            self.skipTest("multiplate separated filaments.3mf not available")

        # Test with invalid plate index
        plate_requirements = (
            self.model_service.get_plate_specific_filament_requirements(
                multiplate_file, 999
            )
        )
        self.assertIsNone(plate_requirements)

    def test_single_plate_model_consistency(self):
        """Test that single-plate models return consistent requirements."""
        single_plate_file = self.test_files_dir / "multicolor-test-coin.3mf"

        if not single_plate_file.exists():
            self.skipTest("multicolor-test-coin.3mf not available")

        full_requirements = self.model_service.parse_3mf_filament_requirements(
            single_plate_file
        )
        if not full_requirements:
            self.skipTest("No filament requirements in single plate file")

        # For single-plate models, plate-specific should match full requirements
        # or be simplified version
        plate_requirements = (
            self.model_service.get_plate_specific_filament_requirements(
                single_plate_file, 1
            )
        )

        if plate_requirements:
            # Should be equal or less than full requirements
            self.assertLessEqual(
                plate_requirements.filament_count, full_requirements.filament_count
            )


if __name__ == "__main__":
    unittest.main()
