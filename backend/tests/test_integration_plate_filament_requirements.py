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
        """Test that all filaments are returned for each plate (design decision)."""
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

        # Per design decision, all plates return all configured filaments
        # to support proper AMS mapping for multi-color models

        # Test plate-specific requirements for each plate
        for plate in plates:
            plate_requirements = (
                self.model_service.get_plate_specific_filament_requirements(
                    multiplate_file, plate.index
                )
            )

            # Should return valid requirements
            self.assertIsNotNone(plate_requirements)

            # Plate requirements should equal full requirements (design decision)
            self.assertEqual(
                plate_requirements.filament_count,
                full_requirements.filament_count,
                f"Plate {plate.index} should return all "
                f"{full_requirements.filament_count} filaments",
            )

            # Should have all filaments
            self.assertEqual(plate_requirements.filament_count, 13)

            # Filament types should match full model types
            self.assertEqual(
                plate_requirements.filament_types,
                full_requirements.filament_types,
                f"Plate {plate.index} types should match full model types",
            )

            # Filament colors should match full model colors
            self.assertEqual(
                plate_requirements.filament_colors,
                full_requirements.filament_colors,
                f"Plate {plate.index} colors should match full model colors",
            )

            print(
                f"Plate {plate.index}: {plate_requirements.filament_count} filaments "
                f"(same as full model)"
            )

    def test_specific_filament_types_per_plate(self):
        """Test that all filaments are returned for each plate (design decision)."""
        multiplate_file = self.test_files_dir / "multiplate separated filaments.3mf"

        if not multiplate_file.exists():
            self.skipTest("multiplate separated filaments.3mf not available")

        # Per design decision, all plates return all configured filaments
        # Get full model requirements for comparison
        full_requirements = self.model_service.parse_3mf_filament_requirements(
            multiplate_file
        )
        self.assertIsNotNone(full_requirements)
        self.assertEqual(full_requirements.filament_count, 13)

        # Test each plate returns all filaments
        for plate_index in [1, 2, 3, 4]:
            plate_requirements = (
                self.model_service.get_plate_specific_filament_requirements(
                    multiplate_file, plate_index
                )
            )

            self.assertIsNotNone(plate_requirements)
            self.assertEqual(
                plate_requirements.filament_types,
                full_requirements.filament_types,
                f"Plate {plate_index} should have all filament types",
            )
            self.assertEqual(
                plate_requirements.filament_colors,
                full_requirements.filament_colors,
                f"Plate {plate_index} should have all colors",
            )
            self.assertEqual(
                plate_requirements.filament_count,
                13,
                f"Plate {plate_index} should have all 13 filaments",
            )

        print("All plates return full filament requirements as per design")

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
