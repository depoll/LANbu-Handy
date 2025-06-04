"""
Tests for the FilamentMatchingService.

Tests the automatic matching logic between model filament requirements
and available AMS filaments.
"""

import pytest
from app.filament_matching_service import (
    FilamentMatch,
    FilamentMatchingResult,
    FilamentMatchingService,
)
from app.model_service import FilamentRequirement
from app.printer_service import AMSFilament, AMSStatusResult, AMSUnit


@pytest.fixture
def service():
    """Create a FilamentMatchingService instance."""
    return FilamentMatchingService()


@pytest.fixture
def simple_ams_status():
    """Create a simple AMS status with a few filaments."""
    filaments = [
        AMSFilament(slot_id=0, filament_type="PLA", color="#FF0000"),  # Red PLA
        AMSFilament(slot_id=1, filament_type="PLA", color="#00FF00"),  # Green PLA
        AMSFilament(slot_id=2, filament_type="PETG", color="#0000FF"),  # Blue PETG
    ]
    ams_unit = AMSUnit(unit_id=0, filaments=filaments)

    return AMSStatusResult(
        success=True, message="AMS status retrieved", ams_units=[ams_unit]
    )


@pytest.fixture
def multi_unit_ams_status():
    """Create AMS status with multiple units."""
    unit1_filaments = [
        AMSFilament(slot_id=0, filament_type="PLA", color="#FF0000"),  # Red PLA
        AMSFilament(slot_id=1, filament_type="PLA", color="#00FF00"),  # Green PLA
    ]
    unit2_filaments = [
        AMSFilament(slot_id=0, filament_type="PETG", color="#0000FF"),  # Blue PETG
        AMSFilament(slot_id=1, filament_type="ABS", color="#FFFF00"),  # Yellow ABS
    ]

    return AMSStatusResult(
        success=True,
        message="AMS status retrieved",
        ams_units=[
            AMSUnit(unit_id=0, filaments=unit1_filaments),
            AMSUnit(unit_id=1, filaments=unit2_filaments),
        ],
    )


class TestFilamentMatchingDataClasses:
    """Test the data classes used in filament matching."""

    def test_filament_match_creation(self):
        """Test FilamentMatch creation."""
        ams_filament = AMSFilament(
            slot_id=0, filament_type="PLA", color="#FF0000", material_id="PLA_RED"
        )

        match = FilamentMatch(
            requirement_index=0,
            ams_unit_id=0,
            ams_slot_id=0,
            match_quality="perfect",
            confidence=0.95,
            ams_filament=ams_filament,
        )

        assert match.requirement_index == 0
        assert match.ams_unit_id == 0
        assert match.ams_slot_id == 0
        assert match.match_quality == "perfect"
        assert match.confidence == 0.95
        assert match.ams_filament == ams_filament

    def test_filament_matching_result_success(self):
        """Test FilamentMatchingResult for successful matching."""
        matches = [
            FilamentMatch(0, 0, 0, "perfect", 0.95),
            FilamentMatch(1, 0, 1, "type_only", 0.7),
        ]

        result = FilamentMatchingResult(
            success=True, message="Matched 2 of 2 required filaments", matches=matches
        )

        assert result.success is True
        assert "Matched 2 of 2" in result.message
        assert len(result.matches) == 2
        assert result.unmatched_requirements is None
        assert result.error_details is None

    def test_filament_matching_result_partial(self):
        """Test FilamentMatchingResult for partial matching."""
        matches = [FilamentMatch(0, 0, 0, "perfect", 0.95)]
        unmatched = [1, 2]

        result = FilamentMatchingResult(
            success=True,
            message="Matched 1 of 3 required filaments",
            matches=matches,
            unmatched_requirements=unmatched,
        )

        assert result.success is True
        assert len(result.matches) == 1
        assert result.unmatched_requirements == [1, 2]


class TestFilamentMatchingService:
    """Test the FilamentMatchingService class."""

    def test_service_creation(self, service):
        """Test that service can be created."""
        assert isinstance(service, FilamentMatchingService)
        assert hasattr(service, "match_filaments")


class TestBasicMatching:
    """Test basic filament matching scenarios."""

    def test_perfect_single_match(self, service, simple_ams_status):
        """Test perfect match for single filament requirement."""
        requirements = FilamentRequirement(
            filament_count=1, filament_types=["PLA"], filament_colors=["#FF0000"]  # Red
        )

        result = service.match_filaments(requirements, simple_ams_status)

        assert result.success is True
        assert len(result.matches) == 1
        assert result.matches[0].match_quality == "perfect"
        assert result.matches[0].ams_unit_id == 0
        assert result.matches[0].ams_slot_id == 0
        assert result.matches[0].confidence > 0.8

    def test_multiple_perfect_matches(self, service, simple_ams_status):
        """Test perfect matches for multiple filament requirements."""
        requirements = FilamentRequirement(
            filament_count=2,
            filament_types=["PLA", "PETG"],
            filament_colors=["#FF0000", "#0000FF"],  # Red, Blue
        )

        result = service.match_filaments(requirements, simple_ams_status)

        assert result.success is True
        assert len(result.matches) == 2

        # Check first match (Red PLA)
        red_match = next(m for m in result.matches if m.requirement_index == 0)
        assert red_match.match_quality == "perfect"
        assert red_match.ams_slot_id == 0

        # Check second match (Blue PETG)
        blue_match = next(m for m in result.matches if m.requirement_index == 1)
        assert blue_match.match_quality == "perfect"
        assert blue_match.ams_slot_id == 2

    def test_type_only_match(self, service, simple_ams_status):
        """Test type-only match when color doesn't match well."""
        requirements = FilamentRequirement(
            filament_count=1,
            filament_types=["PLA"],
            filament_colors=["#FFFFFF"],  # White (not available)
        )

        result = service.match_filaments(requirements, simple_ams_status)

        assert result.success is True
        assert len(result.matches) == 1
        assert result.matches[0].match_quality == "type_only"
        assert result.matches[0].ams_filament.filament_type == "PLA"

    def test_no_type_match_fallback(self, service, simple_ams_status):
        """Test fallback matching when type doesn't match but color is close."""
        requirements = FilamentRequirement(
            filament_count=1,
            filament_types=["ABS"],  # Not available
            filament_colors=["#FF0000"],  # Red (available in PLA)
        )

        result = service.match_filaments(requirements, simple_ams_status)

        assert result.success is True
        assert len(result.matches) == 1
        assert result.matches[0].match_quality == "fallback"
        assert result.matches[0].ams_filament.color == "#FF0000"


class TestColorMatching:
    """Test color matching logic."""

    def test_hex_color_exact_match(self, service):
        """Test exact hex color matching."""
        similarity = service._calculate_color_similarity("#FF0000", "#FF0000")
        assert similarity == 1.0

    def test_hex_color_similar_match(self, service):
        """Test similar hex color matching."""
        similarity = service._calculate_color_similarity("#FF0000", "#FE0000")
        assert similarity > 0.9

    def test_hex_color_different_match(self, service):
        """Test different hex color matching."""
        similarity = service._calculate_color_similarity("#FF0000", "#00FF00")
        assert similarity < 0.5

    def test_color_name_matching(self, service):
        """Test color name to hex conversion and matching."""
        # Test name to name
        similarity = service._calculate_color_similarity("red", "red")
        assert similarity == 1.0

        # Test name to hex
        similarity = service._calculate_color_similarity("red", "#FF0000")
        assert similarity == 1.0

        # Test hex to name
        similarity = service._calculate_color_similarity("#FF0000", "red")
        assert similarity == 1.0

    def test_normalize_color_to_hex(self, service):
        """Test color normalization."""
        assert service._normalize_color_to_hex("#FF0000") == "#FF0000"
        assert service._normalize_color_to_hex("red") == "#FF0000"
        assert service._normalize_color_to_hex("RED") == "#FF0000"
        assert service._normalize_color_to_hex("  red  ") == "#FF0000"
        assert service._normalize_color_to_hex("invalid") is None
        assert service._normalize_color_to_hex("#GGGGGG") is None


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_failed_ams_status(self, service):
        """Test handling of failed AMS status."""
        failed_status = AMSStatusResult(
            success=False,
            message="AMS query failed",
            error_details="Connection timeout",
        )

        requirements = FilamentRequirement(
            filament_count=1, filament_types=["PLA"], filament_colors=["#FF0000"]
        )

        result = service.match_filaments(requirements, failed_status)

        assert result.success is False
        assert "AMS status not available" in result.message
        assert len(result.matches) == 0

    def test_empty_ams_units(self, service):
        """Test handling of empty AMS units."""
        empty_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[]
        )

        requirements = FilamentRequirement(
            filament_count=1, filament_types=["PLA"], filament_colors=["#FF0000"]
        )

        result = service.match_filaments(requirements, empty_status)

        assert result.success is False
        assert "no AMS units found" in result.message

    def test_no_loaded_filaments(self, service):
        """Test handling of AMS units with no loaded filaments."""
        empty_unit = AMSUnit(unit_id=0, filaments=[])
        empty_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[empty_unit]
        )

        requirements = FilamentRequirement(
            filament_count=1, filament_types=["PLA"], filament_colors=["#FF0000"]
        )

        result = service.match_filaments(requirements, empty_status)

        assert result.success is False
        assert "No filaments found in AMS units" in result.message

    def test_no_requirements(self, service, simple_ams_status):
        """Test handling of empty filament requirements."""
        requirements = FilamentRequirement(
            filament_count=0, filament_types=[], filament_colors=[]
        )

        result = service.match_filaments(requirements, simple_ams_status)

        assert result.success is False
        assert "No filament requirements specified" in result.message

    def test_unmatched_requirements(self, service, simple_ams_status):
        """Test handling when some requirements can't be matched."""
        requirements = FilamentRequirement(
            filament_count=3,
            filament_types=["PLA", "TPU", "WOOD"],  # TPU and WOOD not available
            filament_colors=["#FF0000", "#000000", "#8B4513"],
        )

        result = service.match_filaments(requirements, simple_ams_status)

        assert result.success is True  # At least one match found
        assert len(result.matches) == 1  # Only PLA should match
        assert result.unmatched_requirements is not None
        assert len(result.unmatched_requirements) == 2


class TestAdvancedScenarios:
    """Test advanced matching scenarios."""

    def test_allow_double_assignment_with_penalty(self, service, simple_ams_status):
        """Test that double assignment is allowed but with lower confidence."""
        requirements = FilamentRequirement(
            filament_count=2,
            filament_types=["PLA", "PLA"],
            filament_colors=["#FF0000", "#FF0000"],  # Both want red PLA
        )

        result = service.match_filaments(requirements, simple_ams_status)

        assert result.success is True
        assert len(result.matches) == 2

        # Check that both requirements are matched
        req_indices = {match.requirement_index for match in result.matches}
        assert req_indices == {0, 1}

        # If there's a better match available, it should be preferred
        # But if there's double assignment, the second one should have lower confidence
        matches_by_req = {match.requirement_index: match for match in result.matches}
        match_0 = matches_by_req[0]
        match_1 = matches_by_req[1]

        # One should be the preferred match, the other might be double assignment
        if match_0.ams_slot_id == match_1.ams_slot_id:
            # Double assignment occurred - one should have lower confidence
            confidences = [match_0.confidence, match_1.confidence]
            confidences.sort(reverse=True)
            # The lower confidence should be significantly lower (60% penalty)
            assert confidences[1] < confidences[0] * 0.7
        else:
            # Different slots used - both should have similar high confidence
            assert match_0.confidence > 0.8
            assert match_1.confidence > 0.8

    def test_forced_double_assignment(self, service):
        """Test double assignment when there's only one suitable slot."""
        # AMS with only one PLA filament
        filaments = [
            AMSFilament(slot_id=0, filament_type="PLA", color="#FF0000"),  # Red PLA
            AMSFilament(slot_id=1, filament_type="PETG", color="#00FF00"),  # Green PETG
        ]
        ams_unit = AMSUnit(unit_id=0, filaments=filaments)
        ams_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[ams_unit]
        )

        # Model requires two PLA filaments
        requirements = FilamentRequirement(
            filament_count=2,
            filament_types=["PLA", "PLA"],
            filament_colors=["#FF0000", "#FF0000"],  # Both want red PLA
        )

        result = service.match_filaments(requirements, ams_status)

        assert result.success is True
        assert len(result.matches) == 2

        # Both should use the same slot (double assignment)
        assert result.matches[0].ams_slot_id == result.matches[1].ams_slot_id == 0

        # One should have full confidence, the other reduced
        confidences = [result.matches[0].confidence, result.matches[1].confidence]
        confidences.sort(reverse=True)

        # First match should have normal confidence
        assert confidences[0] > 0.8

        # Second match should have reduced confidence (60% penalty)
        expected_reduced = confidences[0] * 0.6
        assert abs(confidences[1] - expected_reduced) < 0.05

    def test_multi_unit_matching(self, service, multi_unit_ams_status):
        """Test matching across multiple AMS units."""
        requirements = FilamentRequirement(
            filament_count=3,
            filament_types=["PLA", "PETG", "ABS"],
            filament_colors=["#FF0000", "#0000FF", "#FFFF00"],
        )

        result = service.match_filaments(requirements, multi_unit_ams_status)

        assert result.success is True
        assert len(result.matches) == 3

        # Check that matches span multiple units
        unit_ids = {match.ams_unit_id for match in result.matches}
        assert len(unit_ids) == 2  # Should use both units

    def test_match_quality_prioritization(self, service):
        """Test that better matches are prioritized."""
        # Create AMS with perfect and imperfect matches
        filaments = [
            AMSFilament(slot_id=0, filament_type="PLA", color="#FF0000"),  # Perfect
            AMSFilament(slot_id=1, filament_type="PLA", color="#FE0000"),  # Close color
            AMSFilament(slot_id=2, filament_type="PETG", color="#FF0000"),  # Wrong type
        ]
        ams_unit = AMSUnit(unit_id=0, filaments=filaments)
        ams_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[ams_unit]
        )

        requirements = FilamentRequirement(
            filament_count=1, filament_types=["PLA"], filament_colors=["#FF0000"]
        )

        result = service.match_filaments(requirements, ams_status)

        assert result.success is True
        assert len(result.matches) == 1
        # Should pick the perfect match (slot 0) over close matches
        assert result.matches[0].ams_slot_id == 0
        assert result.matches[0].match_quality == "perfect"


class TestIntegration:
    """Integration tests with realistic scenarios."""

    def test_realistic_multicolor_print(self, service):
        """Test realistic multicolor print scenario."""
        # Simulate a realistic AMS setup
        filaments = [
            AMSFilament(
                slot_id=0,
                filament_type="PLA",
                color="White",
                material_id="BAMBU_PLA_WHITE",
            ),
            AMSFilament(
                slot_id=1,
                filament_type="PLA",
                color="Black",
                material_id="BAMBU_PLA_BLACK",
            ),
            AMSFilament(
                slot_id=2, filament_type="PLA", color="Red", material_id="BAMBU_PLA_RED"
            ),
            AMSFilament(
                slot_id=3,
                filament_type="PETG",
                color="Blue",
                material_id="BAMBU_PETG_BLUE",
            ),
        ]
        ams_unit = AMSUnit(unit_id=0, filaments=filaments)
        ams_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[ams_unit]
        )

        # Model requiring white and red PLA
        requirements = FilamentRequirement(
            filament_count=2,
            filament_types=["PLA", "PLA"],
            filament_colors=["#FFFFFF", "#FF0000"],
        )

        result = service.match_filaments(requirements, ams_status)

        assert result.success is True
        assert len(result.matches) == 2
        assert result.unmatched_requirements is None

        # Verify specific matches
        white_match = next(m for m in result.matches if m.requirement_index == 0)
        red_match = next(m for m in result.matches if m.requirement_index == 1)

        assert white_match.ams_slot_id == 0  # White slot
        assert red_match.ams_slot_id == 2  # Red slot


class TestCloseTypeMatching:
    """Test close filament type matching functionality."""

    def test_types_compatible_exact_match(self, service):
        """Test exact type matching."""
        assert service._types_compatible("PLA", "PLA") == "exact"
        assert service._types_compatible("PETG", "PETG") == "exact"
        assert service._types_compatible("ABS", "ABS") == "exact"

    def test_types_compatible_case_insensitive(self, service):
        """Test case-insensitive exact matching."""
        assert service._types_compatible("pla", "PLA") == "exact"
        assert service._types_compatible("PLA", "pla") == "exact"
        assert service._types_compatible("petg", "PETG") == "exact"

    def test_types_compatible_close_match_variants(self, service):
        """Test close matching for common filament variants."""
        # PLA variants
        assert service._types_compatible("PLA", "PLA+") == "close"
        assert service._types_compatible("PLA", "PLA-HF") == "close"
        assert service._types_compatible("PLA", "PLAHF") == "close"
        assert service._types_compatible("PLA", "PLA BASIC") == "close"

        # PETG variants
        assert service._types_compatible("PETG", "PETG-HF") == "close"
        assert service._types_compatible("PETG", "PETGHF") == "close"
        assert service._types_compatible("PETG", "PETG-CF") == "close"

        # ABS variants
        assert service._types_compatible("ABS", "ABS+") == "close"
        assert service._types_compatible("ABS", "ABS-HF") == "close"

        # TPU variants
        assert service._types_compatible("TPU", "TPU95A") == "close"
        assert service._types_compatible("TPU", "TPU85A") == "close"

    def test_types_compatible_reverse_matching(self, service):
        """Test that variant to base type also works."""
        assert service._types_compatible("PLA+", "PLA") == "close"
        assert service._types_compatible("PETG-HF", "PETG") == "close"
        assert service._types_compatible("ABS+", "ABS") == "close"

    def test_types_compatible_variant_to_variant(self, service):
        """Test matching between variants of the same base type."""
        assert service._types_compatible("PLA+", "PLA-HF") == "close"
        assert service._types_compatible("PETG-HF", "PETG-CF") == "close"
        assert service._types_compatible("TPU95A", "TPU85A") == "close"

    def test_types_compatible_incompatible(self, service):
        """Test incompatible types return 'none'."""
        assert service._types_compatible("PLA", "PETG") == "none"
        assert service._types_compatible("ABS", "TPU") == "none"
        assert service._types_compatible("PETG", "ABS") == "none"

    def test_close_type_matching_with_good_color(self, service):
        """Test close type match with good color similarity."""
        # AMS has PETG-HF Red, model requires PETG Red
        filaments = [
            AMSFilament(
                slot_id=0, filament_type="PETG-HF", color="#FF0000"
            ),  # Red PETG-HF
        ]
        ams_unit = AMSUnit(unit_id=0, filaments=filaments)
        ams_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[ams_unit]
        )

        requirements = FilamentRequirement(
            filament_count=1,
            filament_types=["PETG"],
            filament_colors=["#FF0000"],  # Red
        )

        result = service.match_filaments(requirements, ams_status)

        assert result.success is True
        assert len(result.matches) == 1
        assert result.matches[0].match_quality == "perfect"
        assert (
            result.matches[0].confidence > 0.9
        )  # High confidence for close type + good color
        assert result.matches[0].ams_filament.filament_type == "PETG-HF"

    def test_close_type_matching_poor_color(self, service):
        """Test close type match with poor color match."""
        # AMS has PLA+ Red, model requires PLA Blue
        filaments = [
            AMSFilament(slot_id=0, filament_type="PLA+", color="#FF0000"),  # Red PLA+
        ]
        ams_unit = AMSUnit(unit_id=0, filaments=filaments)
        ams_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[ams_unit]
        )

        requirements = FilamentRequirement(
            filament_count=1,
            filament_types=["PLA"],
            filament_colors=["#0000FF"],  # Blue
        )

        result = service.match_filaments(requirements, ams_status)

        assert result.success is True
        assert len(result.matches) == 1
        assert result.matches[0].match_quality == "type_only"
        assert (
            result.matches[0].confidence == 0.65
        )  # Lower confidence for close type + poor color
        assert result.matches[0].ams_filament.filament_type == "PLA+"

    def test_close_type_prioritization(self, service):
        """Test that exact type matches are preferred over close type matches."""
        # AMS has both PLA and PLA+, model requires PLA
        filaments = [
            AMSFilament(slot_id=0, filament_type="PLA+", color="#FF0000"),  # Red PLA+
            AMSFilament(
                slot_id=1, filament_type="PLA", color="#FF0000"
            ),  # Red PLA (exact)
        ]
        ams_unit = AMSUnit(unit_id=0, filaments=filaments)
        ams_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[ams_unit]
        )

        requirements = FilamentRequirement(
            filament_count=1, filament_types=["PLA"], filament_colors=["#FF0000"]  # Red
        )

        result = service.match_filaments(requirements, ams_status)

        assert result.success is True
        assert len(result.matches) == 1
        # Should prefer exact PLA match over PLA+ close match
        assert result.matches[0].ams_slot_id == 1  # Exact PLA slot
        assert result.matches[0].ams_filament.filament_type == "PLA"

    def test_multiple_close_matches(self, service):
        """Test handling multiple close type matches."""
        # AMS has PETG-HF and PETG-CF, model requires PETG twice
        filaments = [
            AMSFilament(
                slot_id=0, filament_type="PETG-HF", color="#FF0000"
            ),  # Red PETG-HF
            AMSFilament(
                slot_id=1, filament_type="PETG-CF", color="#00FF00"
            ),  # Green PETG-CF
        ]
        ams_unit = AMSUnit(unit_id=0, filaments=filaments)
        ams_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[ams_unit]
        )

        requirements = FilamentRequirement(
            filament_count=2,
            filament_types=["PETG", "PETG"],
            filament_colors=["#FF0000", "#00FF00"],  # Red, Green
        )

        result = service.match_filaments(requirements, ams_status)

        assert result.success is True
        assert len(result.matches) == 2
        assert all(m.match_quality == "perfect" for m in result.matches)

        # Both should be close matches but with high confidence due to good color match
        for match in result.matches:
            assert match.confidence > 0.9

    def test_mixed_exact_and_close_matches(self, service):
        """Test handling mix of exact and close type matches."""
        # AMS has PLA (exact) and PETG-HF (close), model requires PLA and PETG
        filaments = [
            AMSFilament(
                slot_id=0, filament_type="PLA", color="#FF0000"
            ),  # Red PLA (exact)
            AMSFilament(
                slot_id=1, filament_type="PETG-HF", color="#00FF00"
            ),  # Green PETG-HF (close)
        ]
        ams_unit = AMSUnit(unit_id=0, filaments=filaments)
        ams_status = AMSStatusResult(
            success=True, message="AMS status retrieved", ams_units=[ams_unit]
        )

        requirements = FilamentRequirement(
            filament_count=2,
            filament_types=["PLA", "PETG"],
            filament_colors=["#FF0000", "#00FF00"],  # Red, Green
        )

        result = service.match_filaments(requirements, ams_status)

        assert result.success is True
        assert len(result.matches) == 2

        # Find matches by requirement index
        pla_match = next(m for m in result.matches if m.requirement_index == 0)
        petg_match = next(m for m in result.matches if m.requirement_index == 1)

        # PLA should be exact match with higher confidence
        assert pla_match.ams_filament.filament_type == "PLA"
        assert pla_match.confidence > petg_match.confidence

        # PETG should match to PETG-HF (close match)
        assert petg_match.ams_filament.filament_type == "PETG-HF"
