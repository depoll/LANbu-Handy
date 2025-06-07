"""
Tests for the filament matching API endpoint.

Tests the new /api/filament/match endpoint that exposes the FilamentMatchingService.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

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
        requirement_indices = [match["requirement_index"] for match in result["matches"]]
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
        """Test filament matching with some unmatched requirements."""
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

        assert result["success"] is True  # Should succeed even with partial matches
        assert len(result["matches"]) == 2  # Should match PLA and PETG
        assert result["unmatched_requirements"] == [1]  # TPU should be unmatched

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

        assert result["success"] is False
        assert "AMS status not available or no AMS units found" in result["message"]
        assert result["matches"] == []