"""
Tests for external spool support in LANbu Handy.

Tests the new functionality that allows users to select external spool
instead of AMS slots for filament mapping.
"""

import pytest
from app.filament_matching_service import FilamentMatchingService
from app.model_service import FilamentRequirement
from app.printer_service import AMSFilament, AMSStatusResult, AMSUnit


@pytest.fixture
def service():
    """Create a FilamentMatchingService instance."""
    return FilamentMatchingService()


class TestExternalSpoolSupport:
    """Test external spool functionality."""

    def test_external_spool_when_no_ams(self, service):
        """Test that external spool is suggested when no AMS is available."""
        # Empty AMS status (no units)
        empty_ams_status = AMSStatusResult(
            success=True, message="No AMS detected", ams_units=[]
        )

        requirements = FilamentRequirement(
            filament_count=2,
            filament_types=["PLA", "PETG"],
            filament_colors=["#FF0000", "#00FF00"],
        )

        result = service.match_filaments(requirements, empty_ams_status)

        assert result.success is True
        assert "external spool" in result.message.lower()
        assert len(result.matches) == 2

        # Both matches should be external spool
        for match in result.matches:
            assert match.use_external_spool is True
            assert match.ams_unit_id is None
            assert match.ams_slot_id is None
            assert match.match_quality == "fallback"
            assert match.confidence == 0.5

    def test_external_spool_fallback_for_unmatched(self, service):
        """Test that external spool is used as fallback for unmatched requirements."""
        # AMS with only one PLA filament
        filaments = [
            AMSFilament(slot_id=0, filament_type="PLA", color="#FF0000"),  # Red PLA
        ]
        ams_unit = AMSUnit(unit_id=0, filaments=filaments)
        ams_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[ams_unit]
        )

        # Require PLA and PETG, but only PLA is available in AMS
        requirements = FilamentRequirement(
            filament_count=2,
            filament_types=["PLA", "PETG"],
            filament_colors=["#FF0000", "#0000FF"],
        )

        result = service.match_filaments(requirements, ams_status)

        assert result.success is True
        assert len(result.matches) == 2

        # Find PLA and PETG matches
        pla_match = next(m for m in result.matches if m.requirement_index == 0)
        petg_match = next(m for m in result.matches if m.requirement_index == 1)

        # PLA should use AMS
        assert pla_match.use_external_spool is False
        assert pla_match.ams_unit_id == 0
        assert pla_match.ams_slot_id == 0

        # PETG should use external spool
        assert petg_match.use_external_spool is True
        assert petg_match.ams_unit_id is None
        assert petg_match.ams_slot_id is None

    def test_mixed_ams_and_external_message(self, service):
        """Test that the result message correctly reports mixed AMS and external usage."""
        # AMS with only one filament
        filaments = [
            AMSFilament(slot_id=0, filament_type="PLA", color="#FF0000"),
        ]
        ams_unit = AMSUnit(unit_id=0, filaments=filaments)
        ams_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[ams_unit]
        )

        requirements = FilamentRequirement(
            filament_count=3,
            filament_types=["PLA", "PETG", "ABS"],
            filament_colors=["#FF0000", "#0000FF", "#FFFF00"],
        )

        result = service.match_filaments(requirements, ams_status)

        assert result.success is True
        assert "1 requirements to AMS, 2 to external spool" in result.message

    def test_all_ams_matches_message(self, service):
        """Test message when all requirements are matched to AMS."""
        # AMS with multiple filaments
        filaments = [
            AMSFilament(slot_id=0, filament_type="PLA", color="#FF0000"),
            AMSFilament(slot_id=1, filament_type="PETG", color="#0000FF"),
        ]
        ams_unit = AMSUnit(unit_id=0, filaments=filaments)
        ams_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[ams_unit]
        )

        requirements = FilamentRequirement(
            filament_count=2,
            filament_types=["PLA", "PETG"],
            filament_colors=["#FF0000", "#0000FF"],
        )

        result = service.match_filaments(requirements, ams_status)

        assert result.success is True
        assert "Matched all 2 requirements to AMS" in result.message

        # Both matches should be AMS
        for match in result.matches:
            assert match.use_external_spool is False

    def test_external_spool_confidence_levels(self, service):
        """Test that external spool confidence varies based on context."""
        # Test no AMS case (higher confidence)
        empty_ams_status = AMSStatusResult(
            success=True, message="No AMS detected", ams_units=[]
        )

        requirements = FilamentRequirement(
            filament_count=1, filament_types=["PLA"], filament_colors=["#FF0000"]
        )

        result_no_ams = service.match_filaments(requirements, empty_ams_status)
        no_ams_confidence = result_no_ams.matches[0].confidence

        # Test fallback case (lower confidence)
        filaments = [
            AMSFilament(slot_id=0, filament_type="PETG", color="#0000FF"),  # Different type
        ]
        ams_unit = AMSUnit(unit_id=0, filaments=filaments)
        ams_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[ams_unit]
        )

        result_fallback = service.match_filaments(requirements, ams_status)
        fallback_confidence = result_fallback.matches[0].confidence

        # No AMS case should have higher confidence than fallback case
        assert no_ams_confidence > fallback_confidence
        assert no_ams_confidence == 0.5  # No AMS available
        assert fallback_confidence == 0.3  # Fallback for unmatched