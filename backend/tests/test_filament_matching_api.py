"""
Tests for the filament matching API endpoint.

Tests the new /api/filament/match endpoint that exposes the FilamentMatchingService.
"""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


class TestFilamentMatchingAPI:
    """Test the filament matching API endpoint."""

    def test_match_filaments_successful_match(self):
        """Test successful filament matching with good data."""
        request_data = {
            "filament_requirements": {
                "filament_count": 2,
                "filament_types": ["PLA", "PETG"],
                "filament_colors": ["#FF0000", "#00FF00"],
                "has_multicolor": False,
            },
            "ams_status": {
                "success": True,
                "message": "AMS status retrieved",
                "ams_units": [
                    {
                        "unit_id": 0,
                        "filaments": [
                            {
                                "slot_id": 0,
                                "filament_type": "PLA",
                                "color": "#FF0000",
                                "material_id": "PLA_RED",
                            },
                            {
                                "slot_id": 1,
                                "filament_type": "PETG",
                                "color": "#00FF00",
                                "material_id": "PETG_GREEN",
                            },
                        ],
                    }
                ],
            },
        }

        response = client.post("/api/filament/match", json=request_data)

        assert response.status_code == 200
        result = response.json()

        assert result["success"] is True
        assert "matches" in result
        assert len(result["matches"]) == 2

        # Check that we got matches for both requirements
        requirement_indices = [
            match["requirement_index"] for match in result["matches"]
        ]
        assert 0 in requirement_indices
        assert 1 in requirement_indices

        # Check match quality - should be perfect for exact matches
        for match in result["matches"]:
            assert match["match_quality"] == "perfect"
            assert match["confidence"] > 0.8

    def test_match_filaments_no_ams_status(self):
        """Test filament matching with failed AMS status."""
        request_data = {
            "filament_requirements": {
                "filament_count": 1,
                "filament_types": ["PLA"],
                "filament_colors": ["#FF0000"],
                "has_multicolor": False,
            },
            "ams_status": {
                "success": False,
                "message": "AMS communication failed",
                "ams_units": None,
                "error_details": "Printer not responding",
            },
        }

        response = client.post("/api/filament/match", json=request_data)

        assert response.status_code == 200
        result = response.json()

        assert result["success"] is False
        assert "AMS status not available" in result["message"]
        assert result["matches"] == []

    def test_match_filaments_no_requirements(self):
        """Test filament matching with no filament requirements."""
        request_data = {
            "filament_requirements": {
                "filament_count": 0,
                "filament_types": [],
                "filament_colors": [],
                "has_multicolor": False,
            },
            "ams_status": {
                "success": True,
                "message": "AMS status retrieved",
                "ams_units": [
                    {
                        "unit_id": 0,
                        "filaments": [
                            {
                                "slot_id": 0,
                                "filament_type": "PLA",
                                "color": "#FF0000",
                                "material_id": "PLA_RED",
                            }
                        ],
                    }
                ],
            },
        }

        response = client.post("/api/filament/match", json=request_data)

        assert response.status_code == 200
        result = response.json()

        assert result["success"] is False
        assert "No filament requirements" in result["message"]
        assert result["matches"] == []

    def test_match_filaments_partial_matches(self):
        """Test filament matching when some requirements can't be matched to AMS."""
        request_data = {
            "filament_requirements": {
                "filament_count": 3,
                "filament_types": ["PLA", "TPU", "PETG"],
                "filament_colors": ["#FF0000", "#00FF00", "#0000FF"],
                "has_multicolor": False,
            },
            "ams_status": {
                "success": True,
                "message": "AMS status retrieved",
                "ams_units": [
                    {
                        "unit_id": 0,
                        "filaments": [
                            {
                                "slot_id": 0,
                                "filament_type": "PLA",
                                "color": "#FF0000",
                                "material_id": "PLA_RED",
                            },
                            {
                                "slot_id": 1,
                                "filament_type": "PETG",
                                "color": "#0000FF",
                                "material_id": "PETG_BLUE",
                            },
                        ],
                    }
                ],
            },
        }

        response = client.post("/api/filament/match", json=request_data)

        assert response.status_code == 200
        result = response.json()

        assert result["success"] is True
        assert (
            len(result["matches"]) == 3
        )  # All requirements matched with external spool

        # Since TPU cannot be matched to AMS, ALL filaments should use external spool
        # (no mixing allowed)
        matches = result["matches"]
        pla_match = next(m for m in matches if m["requirement_index"] == 0)
        tpu_match = next(m for m in matches if m["requirement_index"] == 1)
        petg_match = next(m for m in matches if m["requirement_index"] == 2)

        # All should use external spool due to no-mixing constraint
        assert pla_match["use_external_spool"] is True
        assert tpu_match["use_external_spool"] is True
        assert petg_match["use_external_spool"] is True

        # AMS fields should be None for external spool
        assert pla_match["ams_unit_id"] is None
        assert pla_match["ams_slot_id"] is None
        assert tpu_match["ams_unit_id"] is None
        assert tpu_match["ams_slot_id"] is None
        assert petg_match["ams_unit_id"] is None
        assert petg_match["ams_slot_id"] is None

        assert (
            result["unmatched_requirements"] is None
        )  # No unmatched since external spool fallback

    def test_match_filaments_invalid_request(self):
        """Test filament matching with invalid request data."""
        request_data = {
            "filament_requirements": {
                "filament_count": 1,
                # Missing required fields
            },
            "ams_status": {
                "success": True,
                "message": "Test",
            },
        }

        response = client.post("/api/filament/match", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_match_filaments_empty_ams_units(self):
        """Test filament matching with empty AMS units."""
        request_data = {
            "filament_requirements": {
                "filament_count": 1,
                "filament_types": ["PLA"],
                "filament_colors": ["#FF0000"],
                "has_multicolor": False,
            },
            "ams_status": {
                "success": True,
                "message": "AMS status retrieved but no filaments",
                "ams_units": [],
            },
        }

        response = client.post("/api/filament/match", json=request_data)

        assert response.status_code == 200
        result = response.json()

        assert result["success"] is True  # Should succeed with external spool
        assert "No AMS units available" in result["message"]
        assert len(result["matches"]) == 1
        assert result["matches"][0]["use_external_spool"] is True
