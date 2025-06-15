"""
Filament matching service for LANbu Handy.

Handles automatic matching of model filament requirements with available AMS filaments
based on type and color similarity.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.model_service import FilamentRequirement
from app.printer_service import AMSFilament, AMSStatusResult, AMSUnit

logger = logging.getLogger(__name__)


@dataclass
class FilamentMatch:
    """Represents a suggested mapping between model requirement and AMS filament."""

    requirement_index: int  # Index in the model's filament requirements
    ams_unit_id: int
    ams_slot_id: int
    match_quality: str  # "perfect", "type_only", "fallback", "none"
    confidence: float  # 0.0 to 1.0
    ams_filament: Optional[AMSFilament] = None


@dataclass
class FilamentMatchingResult:
    """Result of the filament matching process."""

    success: bool
    message: str
    matches: List[FilamentMatch]
    unmatched_requirements: List[int] = (
        None  # Indices of requirements that couldn't be matched
    )
    error_details: str = None


class FilamentMatchingService:
    """Service for automatically matching model filaments with AMS filaments."""

    # Common color name mappings to approximate hex values
    COLOR_NAME_MAP = {
        "red": "#FF0000",
        "green": "#00FF00",
        "blue": "#0000FF",
        "yellow": "#FFFF00",
        "orange": "#FFA500",
        "purple": "#800080",
        "pink": "#FFC0CB",
        "brown": "#A52A2A",
        "black": "#000000",
        "white": "#FFFFFF",
        "gray": "#808080",
        "grey": "#808080",
    }

    def __init__(self):
        """Initialize the filament matching service."""
        pass

    def match_filaments(
        self, requirements: FilamentRequirement, ams_status: AMSStatusResult
    ) -> FilamentMatchingResult:
        """
        Match model filament requirements with available AMS filaments.

        Args:
            requirements: The model's filament requirements
            ams_status: Current AMS status with available filaments

        Returns:
            FilamentMatchingResult with suggested mappings
        """
        if not ams_status.success or not ams_status.ams_units:
            return FilamentMatchingResult(
                success=False,
                message="AMS status not available or no AMS units found",
                matches=[],
                error_details="Cannot match filaments without valid AMS status",
            )

        if not requirements or requirements.filament_count == 0:
            return FilamentMatchingResult(
                success=False,
                message="No filament requirements specified",
                matches=[],
                error_details="Model has no filament requirements to match",
            )

        # Get all available AMS filaments
        available_filaments = self._get_all_ams_filaments(ams_status.ams_units)

        if not available_filaments:
            return FilamentMatchingResult(
                success=False,
                message="No filaments found in AMS units",
                matches=[],
                error_details="AMS units contain no loaded filaments",
            )

        # Perform the matching
        matches = []
        used_slots = set()  # Track used AMS slots to avoid double assignment
        unmatched_requirements = []

        for req_index in range(requirements.filament_count):
            req_type = (
                requirements.filament_types[req_index]
                if req_index < len(requirements.filament_types)
                else "PLA"
            )
            req_color = (
                requirements.filament_colors[req_index]
                if req_index < len(requirements.filament_colors)
                else "#000000"
            )

            best_match = self._find_best_match(
                req_type, req_color, available_filaments, used_slots
            )

            if best_match:
                # Update the requirement index for this match
                best_match.requirement_index = req_index
                matches.append(best_match)
                used_slots.add((best_match.ams_unit_id, best_match.ams_slot_id))
            else:
                unmatched_requirements.append(req_index)

        success = len(matches) > 0
        message = (
            f"Matched {len(matches)} of {requirements.filament_count} "
            "required filaments"
        )

        if unmatched_requirements:
            message += (
                f". {len(unmatched_requirements)} requirements could not be matched."
            )

        return FilamentMatchingResult(
            success=success,
            message=message,
            matches=matches,
            unmatched_requirements=(
                unmatched_requirements if unmatched_requirements else None
            ),
        )

    def _get_all_ams_filaments(
        self, ams_units: List[AMSUnit]
    ) -> List[Tuple[AMSFilament, int, int]]:
        """
        Get all available AMS filaments across all units.
        Excludes empty slots.

        Returns:
            List of tuples: (AMSFilament, unit_id, slot_id)
        """
        all_filaments = []
        for unit in ams_units:
            for filament in unit.filaments:
                # Skip empty slots
                if filament.filament_type == "Empty":
                    continue
                all_filaments.append((filament, unit.unit_id, filament.slot_id))
        return all_filaments

    def _find_best_match(
        self,
        req_type: str,
        req_color: str,
        available_filaments: List[Tuple[AMSFilament, int, int]],
        used_slots: set,
    ) -> Optional[FilamentMatch]:
        """
        Find the best match for a single filament requirement.

        Args:
            req_type: Required filament type (e.g., "PLA")
            req_color: Required color (hex or name)
            available_filaments: Available AMS filaments
            used_slots: Set of already used (unit_id, slot_id) tuples

        Returns:
            Best FilamentMatch or None if no suitable match found
        """
        candidates = []

        for ams_filament, unit_id, slot_id in available_filaments:
            # Allow double assignment but evaluate with used_slots context
            match = self._evaluate_match(
                req_type, req_color, ams_filament, unit_id, slot_id, used_slots
            )
            if match:
                candidates.append(match)

        if not candidates:
            return None

        # Sort by match quality and confidence (best first)
        candidates.sort(
            key=lambda m: (
                {"perfect": 4, "type_only": 3, "fallback": 2, "none": 1}[
                    m.match_quality
                ],
                m.confidence,
            ),
            reverse=True,
        )

        return candidates[0]

    def _evaluate_match(
        self,
        req_type: str,
        req_color: str,
        ams_filament: AMSFilament,
        unit_id: int,
        slot_id: int,
        used_slots: set = None,
    ) -> Optional[FilamentMatch]:
        """
        Evaluate how well an AMS filament matches a requirement.

        Args:
            req_type: Required filament type
            req_color: Required color (hex or name)
            ams_filament: AMS filament to evaluate
            unit_id: AMS unit ID
            slot_id: AMS slot ID
            used_slots: Set of already used (unit_id, slot_id) tuples

        Returns:
            FilamentMatch with quality and confidence scores,
            or None if no match possible
        """
        # Type compatibility check
        type_compatibility = self._types_compatible(
            req_type, ams_filament.filament_type
        )

        # Color matching
        color_similarity = self._calculate_color_similarity(
            req_color, ams_filament.color
        )

        # Determine match quality and confidence based on type compatibility
        # and color similarity
        if type_compatibility == "exact" and color_similarity > 0.8:
            match_quality = "perfect"
            confidence = (1.0 + color_similarity) / 2.0  # Bias towards perfect matches
        elif type_compatibility == "exact" and color_similarity > 0.5:
            match_quality = "perfect"
            confidence = color_similarity
        elif type_compatibility == "close" and color_similarity > 0.8:
            match_quality = "perfect"
            confidence = color_similarity * 0.95  # Slightly lower than exact type match
        elif type_compatibility == "close" and color_similarity > 0.5:
            match_quality = "perfect"
            confidence = color_similarity * 0.9  # Good close match
        elif type_compatibility == "exact":
            match_quality = "type_only"
            confidence = 0.7  # Good exact type match but poor color
        elif type_compatibility == "close":
            match_quality = "type_only"
            confidence = 0.65  # Good close type match but poor color
        elif color_similarity > 0.8:
            match_quality = "fallback"
            confidence = color_similarity * 0.5  # Lower confidence for type mismatch
        else:
            # Very poor match - don't suggest it
            return None

        # Apply penalty for double assignment (using already used slots)
        if used_slots and (unit_id, slot_id) in used_slots:
            confidence = confidence * 0.6  # Significant penalty for double assignment
            # Don't change match_quality, but heavily penalize confidence

        return FilamentMatch(
            requirement_index=-1,  # Will be set by caller
            ams_unit_id=unit_id,
            ams_slot_id=slot_id,
            match_quality=match_quality,
            confidence=confidence,
            ams_filament=ams_filament,
        )

    def _types_match(self, req_type: str, ams_type: str) -> bool:
        """
        Check if two filament types match exactly.

        Args:
            req_type: Required filament type
            ams_type: AMS filament type

        Returns:
            True if types match exactly (case-insensitive)
        """
        return req_type.upper().strip() == ams_type.upper().strip()

    def _types_compatible(self, req_type: str, ams_type: str) -> str:
        """
        Check filament type compatibility level.

        Args:
            req_type: Required filament type
            ams_type: AMS filament type

        Returns:
            "exact" for exact match, "close" for compatible variants,
            "none" for incompatible
        """
        req_clean = req_type.upper().strip()
        ams_clean = ams_type.upper().strip()

        # Exact match first
        if req_clean == ams_clean:
            return "exact"

        # Define base types and their common variants
        type_variants = {
            "PLA": ["PLA+", "PLA-HF", "PLAHF", "PLA BASIC", "PLA MATTE", "PLA SILK"],
            "PETG": ["PETG-HF", "PETGHF", "PETG-CF", "PETG BASIC"],
            "ABS": ["ABS+", "ABS-HF", "ABSHF", "ABS BASIC"],
            "TPU": ["TPU95A", "TPU95", "TPU85A", "TPU85", "TPU-HF"],
            "ASA": ["ASA+", "ASA-HF", "ASAHF"],
            "PC": ["PC-CF", "PC-ABS"],
            "PA": ["PA-CF", "PA-GF", "PA11-CF", "PA12-CF"],
            "PET": ["PETG", "PETG-HF", "PET-CF"],
        }

        # Check if ams_type is a variant of req_type
        for base_type, variants in type_variants.items():
            if req_clean == base_type and ams_clean in variants:
                return "close"
            # Also check reverse - if req is variant and ams is base
            if ams_clean == base_type and req_clean in variants:
                return "close"

        # Check for bidirectional variant matching
        for base_type, variants in type_variants.items():
            if req_clean in variants and ams_clean in variants:
                return "close"

        return "none"

    def _calculate_color_similarity(self, req_color: str, ams_color: str) -> float:
        """
        Calculate similarity between two colors.

        Args:
            req_color: Required color (hex code or name)
            ams_color: AMS color (hex code or name)

        Returns:
            Similarity score from 0.0 to 1.0
        """
        # Normalize colors to hex codes
        req_hex = self._normalize_color_to_hex(req_color)
        ams_hex = self._normalize_color_to_hex(ams_color)

        if not req_hex or not ams_hex:
            # If we can't parse colors, fall back to string comparison
            return (
                1.0 if req_color.lower().strip() == ams_color.lower().strip() else 0.0
            )

        # Calculate color distance in RGB space
        return self._calculate_rgb_similarity(req_hex, ams_hex)

    def _normalize_color_to_hex(self, color: str) -> Optional[str]:
        """
        Convert a color (name or hex) to a normalized hex code.

        Args:
            color: Color as hex code (#RRGGBB) or name (red, blue, etc.)

        Returns:
            Normalized hex code or None if parsing fails
        """
        if not color:
            return None

        color = color.strip().lower()

        # Check if it's already a hex code
        if color.startswith("#") and len(color) == 7:
            # Validate hex format
            if re.match(r"^#[0-9a-f]{6}$", color):
                return color.upper()

        # Try to map color name to hex
        return self.COLOR_NAME_MAP.get(color)

    def _calculate_rgb_similarity(self, hex1: str, hex2: str) -> float:
        """
        Calculate similarity between two hex colors in RGB space.

        Args:
            hex1: First hex color (#RRGGBB)
            hex2: Second hex color (#RRGGBB)

        Returns:
            Similarity score from 0.0 to 1.0
        """
        try:
            # Parse RGB values
            r1, g1, b1 = int(hex1[1:3], 16), int(hex1[3:5], 16), int(hex1[5:7], 16)
            r2, g2, b2 = int(hex2[1:3], 16), int(hex2[3:5], 16), int(hex2[5:7], 16)

            # Calculate Euclidean distance in RGB space
            distance = ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5

            # Normalize to 0-1 scale (max distance in RGB space is ~441)
            max_distance = (255**2 + 255**2 + 255**2) ** 0.5
            similarity = 1.0 - (distance / max_distance)

            return max(0.0, similarity)
        except (ValueError, IndexError):
            return 0.0
