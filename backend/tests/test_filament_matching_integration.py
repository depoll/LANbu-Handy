"""
Integration test for the filament matching feature.

Tests the complete flow from frontend to backend for filament matching.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestFilamentMatchingIntegration:
    """Test the complete filament matching integration."""

    def test_filament_matching_complete_flow(self):
        """Test the complete flow of filament matching from API perspective."""
        # This simulates the data that would come from the frontend
        # after model analysis and AMS status retrieval

        # Step 1: Test the model submission endpoint (already exists)
        # This is just to verify the flow is intact
        health_response = client.get("/api/health")
        assert health_response.status_code == 200

        # Step 2: Test the filament matching endpoint with realistic data
        request_data = {
            "filament_requirements": {
                "filament_count": 3,
                "filament_types": ["PLA", "PETG", "PLA"],
                "filament_colors": ["#FF0000", "#00FF00", "#FFFF00"],
                "has_multicolor": True,
            },
            "ams_status": {
                "success": True,
                "message": "AMS status retrieved successfully",
                "ams_units": [
                    {
                        "unit_id": 0,
                        "filaments": [
                            {
                                "slot_id": 0,
                                "filament_type": "PLA",
                                "color": "#FF0000",  # Exact match for requirement 0
                                "material_id": "PLA_RED",
                            },
                            {
                                "slot_id": 1,
                                "filament_type": "PETG",
                                "color": "#00FF00",  # Exact match for requirement 1
                                "material_id": "PETG_GREEN",
                            },
                            {
                                "slot_id": 2,
                                "filament_type": "PLA",
                                "color": "#FFFFFF",  # Type match for requirement 2 (different color)
                                "material_id": "PLA_WHITE",
                            },
                            {
                                "slot_id": 3,
                                "filament_type": "ABS",
                                "color": "#0000FF",  # Available but not needed
                                "material_id": "ABS_BLUE",
                            },
                        ],
                    }
                ],
            },
        }

        response = client.post("/api/filament/match", json=request_data)

        # Verify the response
        assert response.status_code == 200
        result = response.json()

        assert result["success"] is True
        assert "matches" in result
        assert len(result["matches"]) == 3  # Should match all 3 requirements

        # Verify the matches are reasonable
        matches = result["matches"]

        # Sort matches by requirement_index for easier testing
        matches.sort(key=lambda x: x["requirement_index"])

        # Check requirement 0 (Red PLA) - should get perfect match
        req0_match = matches[0]
        assert req0_match["requirement_index"] == 0
        assert req0_match["ams_unit_id"] == 0
        assert req0_match["ams_slot_id"] == 0  # Red PLA slot
        assert req0_match["match_quality"] == "perfect"
        assert req0_match["confidence"] > 0.8

        # Check requirement 1 (Green PETG) - should get perfect match
        req1_match = matches[1]
        assert req1_match["requirement_index"] == 1
        assert req1_match["ams_unit_id"] == 0
        assert req1_match["ams_slot_id"] == 1  # Green PETG slot
        assert req1_match["match_quality"] == "perfect"
        assert req1_match["confidence"] > 0.8

        # Check requirement 2 (Yellow PLA) - should get type-only match with white PLA
        req2_match = matches[2]
        assert req2_match["requirement_index"] == 2
        assert req2_match["ams_unit_id"] == 0
        assert req2_match["ams_slot_id"] == 2  # White PLA slot
        # Could be "perfect" or "type_only" depending on color matching algorithm
        assert req2_match["match_quality"] in ["perfect", "type_only"]
        assert req2_match["confidence"] > 0.0

        # Verify no unmatched requirements since we have enough filaments
        assert (
            result["unmatched_requirements"] is None
            or len(result["unmatched_requirements"]) == 0
        )

    def test_filament_matching_with_insufficient_ams(self):
        """Test filament matching when AMS doesn't have enough filaments."""
        request_data = {
            "filament_requirements": {
                "filament_count": 3,
                "filament_types": ["PLA", "PETG", "TPU"],
                "filament_colors": ["#FF0000", "#00FF00", "#0000FF"],
                "has_multicolor": False,
            },
            "ams_status": {
                "success": True,
                "message": "AMS status retrieved successfully",
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
                            # No TPU available
                        ],
                    }
                ],
            },
        }

        response = client.post("/api/filament/match", json=request_data)

        assert response.status_code == 200
        result = response.json()

        assert result["success"] is True  # Still successful even with partial matches
        assert len(result["matches"]) == 2  # Should match PLA and PETG
        assert result["unmatched_requirements"] == [2]  # TPU requirement unmatched

    def test_filament_matching_error_cases(self):
        """Test error cases for filament matching."""
        # Test with invalid filament requirements
        invalid_request = {
            "filament_requirements": {
                "filament_count": -1,  # Invalid count
                "filament_types": [],
                "filament_colors": [],
                "has_multicolor": False,
            },
            "ams_status": {
                "success": True,
                "message": "Test",
                "ams_units": [],
            },
        }

        response = client.post("/api/filament/match", json=invalid_request)
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is False
