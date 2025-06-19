"""
Tests for external spool support (no mixing constraint) in LANbu Handy.

Tests the constraint that either ALL filaments use AMS slots OR ALL use external spool.
No mixing is allowed.
"""

import pytest
from app.filament_matching_service import FilamentMatchingService
from app.model_service import FilamentRequirement
from app.printer_service import AMSFilament, AMSStatusResult, AMSUnit


@pytest.fixture
def service():
    """Create a FilamentMatchingService instance."""
    return FilamentMatchingService()


class TestExternalSpoolNoMixing:
    """Test external spool functionality with no mixing constraint."""

    def test_all_ams_when_all_can_match(self, service):
        """Test that AMS is used for all when all requirements can be matched."""
        # AMS with multiple filaments that can match requirements
        filaments = [
            AMSFilament(slot_id=0, filament_type="PLA", color="#FF0000"),  # Red PLA
            AMSFilament(slot_id=1, filament_type="PETG", color="#0000FF"),  # Blue PETG
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
        assert "all 2 requirements to AMS" in result.message
        assert len(result.matches) == 2

        # All matches should be AMS (no external spool)
        for match in result.matches:
            assert match.use_external_spool is False
            assert match.ams_unit_id is not None
            assert match.ams_slot_id is not None

    def test_all_external_when_any_cannot_match(self, service):
        """Test that external spool is used for ALL when ANY requirement can't be matched to AMS."""
        # AMS with only one PLA filament
        filaments = [
            AMSFilament(
                slot_id=0, filament_type="PLA", color="#FF0000"
            ),  # Red PLA only
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
        assert "external spool for all" in result.message
        assert len(result.matches) == 2

        # ALL matches should be external spool (no AMS)
        for match in result.matches:
            assert match.use_external_spool is True
            assert match.ams_unit_id is None
            assert match.ams_slot_id is None
            assert match.match_quality == "fallback"

    def test_all_external_when_no_ams(self, service):
        """Test that external spool is used for all when no AMS is available."""
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
        assert "external spool for all" in result.message
        assert len(result.matches) == 2

        # All matches should be external spool
        for match in result.matches:
            assert match.use_external_spool is True
            assert match.ams_unit_id is None
            assert match.ams_slot_id is None
            assert match.match_quality == "fallback"
            assert match.confidence == 0.7  # Higher confidence when AMS not available

    def test_all_external_when_no_filaments_in_ams(self, service):
        """Test that external spool is used for all when AMS has no loaded filaments."""
        # AMS with only empty slots
        filaments = [
            AMSFilament(slot_id=0, filament_type="Empty", color="#000000"),
            AMSFilament(slot_id=1, filament_type="Empty", color="#000000"),
        ]
        ams_unit = AMSUnit(unit_id=0, filaments=filaments)
        ams_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[ams_unit]
        )

        requirements = FilamentRequirement(
            filament_count=1,
            filament_types=["PLA"],
            filament_colors=["#FF0000"],
        )

        result = service.match_filaments(requirements, ams_status)

        assert result.success is True
        assert "external spool for all" in result.message
        assert len(result.matches) == 1

        # Should be external spool
        match = result.matches[0]
        assert match.use_external_spool is True
        assert match.ams_unit_id is None
        assert match.ams_slot_id is None
        assert match.match_quality == "fallback"

    def test_confidence_levels(self, service):
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
            AMSFilament(
                slot_id=0, filament_type="PETG", color="#0000FF"
            ),  # Different type
        ]
        ams_unit = AMSUnit(unit_id=0, filaments=filaments)
        ams_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[ams_unit]
        )

        result_fallback = service.match_filaments(requirements, ams_status)
        fallback_confidence = result_fallback.matches[0].confidence

        # No AMS case should have higher confidence than fallback case
        assert no_ams_confidence > fallback_confidence
        assert no_ams_confidence == 0.7  # No AMS available
        assert fallback_confidence == 0.5  # Fallback for unmatched
