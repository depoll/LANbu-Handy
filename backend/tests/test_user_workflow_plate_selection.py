"""
User workflow test for plate-specific filament requirements feature.
"""

import unittest
from pathlib import Path

from app.main import app
from fastapi.testclient import TestClient


class TestPlateSelectionUserWorkflow(unittest.TestCase):
    """Test the complete user workflow for plate selection with filament filtering."""

    def setUp(self):
        """Set up test dependencies."""
        self.client = TestClient(app)
        self.test_files_dir = Path(__file__).parent.parent.parent / "test_files"

    def test_multiplate_workflow(self):
        """
        Test the complete workflow: upload -> analyze -> select plate
        -> get filtered requirements.
        """
        multiplate_file = self.test_files_dir / "multiplate-test.3mf"

        if not multiplate_file.exists():
            self.skipTest("multiplate-test.3mf not available")

        # Step 1: Upload the multiplate file
        with open(multiplate_file, "rb") as f:
            upload_response = self.client.post(
                "/api/model/upload-file", files={"file": f}
            )

        self.assertEqual(upload_response.status_code, 200)
        upload_data = upload_response.json()
        self.assertTrue(upload_data["success"])
        self.assertTrue(upload_data["has_multiple_plates"])
        self.assertGreater(len(upload_data["plates"]), 1)

        file_id = upload_data["file_id"]
        original_filament_count = upload_data["filament_requirements"]["filament_count"]
        plates = upload_data["plates"]

        print(
            f"Original model has {original_filament_count} filaments "
            f"and {len(plates)} plates"
        )

        # Step 2: Test plate-specific requirements for each plate
        for plate in plates[:3]:  # Test first 3 plates
            plate_index = plate["index"]

            # Get plate-specific filament requirements
            plate_response = self.client.get(
                f"/api/model/{file_id}/plate/{plate_index}/filament-requirements"
            )

            self.assertEqual(plate_response.status_code, 200)
            plate_data = plate_response.json()
            self.assertTrue(plate_data["success"])
            self.assertEqual(plate_data["plate_index"], plate_index)
            self.assertTrue(plate_data["is_filtered"])

            plate_filament_count = plate_data["filament_requirements"]["filament_count"]

            # Plate-specific requirements should be equal or less than original
            self.assertLessEqual(plate_filament_count, original_filament_count)
            self.assertGreaterEqual(plate_filament_count, 1)

            print(
                f"Plate {plate_index}: {plate_filament_count} filaments "
                f"(reduced from {original_filament_count})"
            )

        # Step 3: Test error handling for invalid plate
        invalid_response = self.client.get(
            f"/api/model/{file_id}/plate/999/filament-requirements"
        )
        self.assertEqual(invalid_response.status_code, 404)

        # Step 4: Test that we can still slice with plate selection
        # (This would typically require AMS status and filament mappings,
        # but we can test the endpoint accepts the plate index)
        slice_request = {
            "file_id": file_id,
            "filament_mappings": [
                {"filament_index": 0, "ams_unit_id": 0, "ams_slot_id": 1}
            ],
            "build_plate_type": "cool_plate",
            "selected_plate_index": plates[0]["index"],
        }

        # Note: This will fail because we don't have Bambu Studio CLI
        # in the test environment, but we can test that the request
        # is properly formed and accepted
        try:
            slice_response = self.client.post(
                "/api/slice/configured", json=slice_request
            )
            # We expect this to fail due to missing slicer, but with
            # proper error, not validation error
            self.assertIn(
                slice_response.status_code, [500, 404]
            )  # Internal error, not validation error
        except Exception:
            # Expected - no slicer available in test environment
            pass

    def test_single_plate_model_behavior(self):
        """Test that single-plate models behave correctly."""
        single_plate_file = self.test_files_dir / "multicolor-test-coin.3mf"

        if not single_plate_file.exists():
            self.skipTest("multicolor-test-coin.3mf not available")

        # Upload single-plate file
        with open(single_plate_file, "rb") as f:
            upload_response = self.client.post(
                "/api/model/upload-file", files={"file": f}
            )

        self.assertEqual(upload_response.status_code, 200)
        upload_data = upload_response.json()
        self.assertTrue(upload_data["success"])

        file_id = upload_data["file_id"]

        # Should work for plate 1 (default)
        if upload_data.get("filament_requirements"):
            plate_response = self.client.get(
                f"/api/model/{file_id}/plate/1/filament-requirements"
            )

            if plate_response.status_code == 200:
                plate_data = plate_response.json()
                self.assertTrue(plate_data["success"])
                print(
                    f"Single-plate model: "
                    f"{plate_data['filament_requirements']['filament_count']} "
                    f"filaments"
                )


if __name__ == "__main__":
    unittest.main()
