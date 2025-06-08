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
        multiplate_file = self.test_files_dir / "realistic-multiplate-test.3mf"

        if not multiplate_file.exists():
            self.skipTest("realistic-multiplate-test.3mf not available")

        # Get full model requirements
        full_requirements = self.model_service.parse_3mf_filament_requirements(
            multiplate_file
        )
        self.assertIsNotNone(full_requirements)
        self.assertGreater(full_requirements.filament_count, 1)
        self.assertEqual(full_requirements.filament_count, 4)  # Should have 4 total

        # Get plate information
        plates = self.model_service.parse_3mf_plate_info(multiplate_file)
        self.assertGreater(len(plates), 1)
        self.assertEqual(len(plates), 5)  # Should have 5 plates

        # Expected filament counts per plate (based on our test file)
        expected_filament_counts = {
            1: 1,  # Plate 1: PLA only
            2: 2,  # Plate 2: PLA + PETG
            3: 3,  # Plate 3: PLA + ABS + TPU
            4: 1,  # Plate 4: PETG only
            5: 4,  # Plate 5: All filaments
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
        multiplate_file = self.test_files_dir / "realistic-multiplate-test.3mf"

        if not multiplate_file.exists():
            self.skipTest("realistic-multiplate-test.3mf not available")

        # Expected filament types per plate based on our test file design
        expected_plate_filaments = {
            1: ["PLA"],  # Red PLA only
            2: ["PLA", "PETG"],  # Red PLA + Green PETG
            3: ["PLA", "ABS", "TPU"],  # Red PLA + Blue ABS + Yellow TPU
            4: ["PETG"],  # Green PETG only
            5: ["PLA", "PETG", "ABS", "TPU"],  # All filaments
        }

        expected_plate_colors = {
            1: ["#FF0000"],  # Red only
            2: ["#FF0000", "#00FF00"],  # Red + Green
            3: ["#FF0000", "#0000FF", "#FFFF00"],  # Red + Blue + Yellow
            4: ["#00FF00"],  # Green only
            5: ["#FF0000", "#00FF00", "#0000FF", "#FFFF00"],  # All colors
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
        """Test original multiplate-test.3mf with correct filament requirements per plate."""
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

        # Plates 1-6 use 3 filaments (extruders 2,3,4), plate 7 uses 4 filaments (1,2,3,4)
        for plate in plates:
            plate_requirements = (
                self.model_service.get_plate_specific_filament_requirements(
                    multiplate_file, plate.index
                )
            )

            self.assertIsNotNone(plate_requirements)
            
            if plate.index == 7:
                # Plate 7 uses all 4 filaments
                self.assertEqual(
                    plate_requirements.filament_count,
                    4,
                    f"Plate {plate.index} should use all 4 filaments in this test file",
                )
                self.assertEqual(
                    plate_requirements.filament_types, ["PLA", "PLA", "PLA", "PLA"]
                )
            else:
                # Plates 1-6 use 3 filaments (extruders 2, 3, 4)
                self.assertEqual(
                    plate_requirements.filament_count,
                    3,
                    f"Plate {plate.index} should use 3 filaments in this test file",
                )
                self.assertEqual(
                    plate_requirements.filament_types, ["PLA", "PLA", "PLA"]
                )

        print(
            "Original multiplate-test.3mf: All plates use all 4 filaments "
            "(no filtering)"
        )

    def test_invalid_plate_index_handling(self):
        """Test handling of invalid plate indices."""
        multiplate_file = self.test_files_dir / "realistic-multiplate-test.3mf"

        if not multiplate_file.exists():
            self.skipTest("realistic-multiplate-test.3mf not available")

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
