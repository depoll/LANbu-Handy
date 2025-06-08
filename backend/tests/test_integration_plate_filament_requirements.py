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
        multiplate_file = self.test_files_dir / "multiplate-test.3mf"

        if not multiplate_file.exists():
            self.skipTest("multiplate-test.3mf not available")

        # Get full model requirements
        full_requirements = self.model_service.parse_3mf_filament_requirements(
            multiplate_file
        )
        self.assertIsNotNone(full_requirements)
        self.assertGreater(full_requirements.filament_count, 1)

        # Get plate information
        plates = self.model_service.parse_3mf_plate_info(multiplate_file)
        self.assertGreater(len(plates), 1)

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

            # Filament types should be a subset of full model types
            for i, plate_type in enumerate(plate_requirements.filament_types):
                if i < len(full_requirements.filament_types):
                    self.assertIn(plate_type, full_requirements.filament_types)

            print(
                f"Plate {plate.index}: {plate_requirements.filament_count} filaments "
                f"(reduced from {full_requirements.filament_count})"
            )

    def test_invalid_plate_index_handling(self):
        """Test handling of invalid plate indices."""
        multiplate_file = self.test_files_dir / "multiplate-test.3mf"

        if not multiplate_file.exists():
            self.skipTest("multiplate-test.3mf not available")

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
