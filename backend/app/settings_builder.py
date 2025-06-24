"""
LANbu Handy - Settings Builder Service

This module provides functionality to build Bambu Studio CLI settings
by selecting appropriate machine, process, and filament profiles based
on the printer model, nozzle size, and material selections.
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default paths to Bambu Studio resources
PROFILES_BASE_PATH = Path("/opt/bambu-studio-resources/profiles/BBL")
MACHINE_PROFILES_PATH = PROFILES_BASE_PATH / "machine"
PROCESS_PROFILES_PATH = PROFILES_BASE_PATH / "process"
FILAMENT_PROFILES_PATH = PROFILES_BASE_PATH / "filament"


class SettingsBuilder:
    """Build Bambu Studio CLI settings from printer and material configuration."""

    # Mapping of printer models to profile names
    PRINTER_MODEL_MAP = {
        "X1C": "Bambu Lab X1 Carbon",
        "X1": "Bambu Lab X1",
        "X1E": "Bambu Lab X1E",
        "P1P": "Bambu Lab P1P",
        "P1S": "Bambu Lab P1S",
        "A1": "Bambu Lab A1",
        "A1 mini": "Bambu Lab A1 mini",
        "H2D": "Bambu Lab H2D",
    }

    # Default print quality profiles by nozzle size
    DEFAULT_QUALITY_PROFILES = {
        0.2: "0.10mm Standard",
        0.4: "0.16mm Optimal",
        0.6: "0.24mm Standard",
        0.8: "0.32mm Standard",
    }

    # Material type mapping for filament profiles
    MATERIAL_TYPE_MAP = {
        "PLA": "Bambu PLA Basic",
        "PLA-CF": "Bambu PLA-CF",
        "PETG": "Bambu PETG Basic",
        "PETG-HF": "Bambu PETG HF",
        "PETG-CF": "Bambu PETG-CF",
        "ABS": "Bambu ABS",
        "ASA": "Bambu ASA",
        "PC": "Bambu PC",
        "PA": "Bambu PA-CF",
        "TPU": "Bambu TPU 95A",
        "PVA": "Bambu Support W",
    }

    def __init__(self, temp_dir: Optional[Path] = None):
        """
        Initialize the settings builder.

        Args:
            temp_dir: Optional temporary directory for generated settings files
        """
        self.temp_dir = (
            temp_dir or Path(tempfile.gettempdir()) / "lanbu-handy" / "settings"
        )
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def build_settings(
        self,
        printer_model: str,
        nozzle_diameter: Optional[float],
        filament_types: List[str],
        print_quality: Optional[str] = None,
        build_plate_type: Optional[str] = None,
        filament_colors: Optional[List[str]] = None,
    ) -> Tuple[Optional[Path], Optional[str]]:
        """
        Build settings files for the given configuration.

        Args:
            printer_model: The printer model (e.g., "X1C", "P1P")
            nozzle_diameter: The nozzle diameter in mm (e.g., 0.4)
            filament_types: List of filament material types
            print_quality: Optional print quality profile name
            build_plate_type: Optional build plate type

        Returns:
            Tuple of (machine_settings_path, filament_settings_string) where
            filament_settings_string is a semicolon-separated list of filament
            file paths
        """
        try:
            # Build machine settings (includes process profile)
            machine_settings_path = self._build_machine_settings(
                printer_model, nozzle_diameter, print_quality
            )

            # Build filament settings
            filament_settings_path = None
            if filament_types:
                filament_settings_path = self._build_filament_settings(
                    printer_model, nozzle_diameter, filament_types, filament_colors
                )

            return machine_settings_path, filament_settings_path

        except Exception as e:
            logger.error(f"Error building settings: {e}")
            return None, None

    def _build_machine_settings(
        self,
        printer_model: str,
        nozzle_diameter: Optional[float],
        print_quality: Optional[str] = None,
    ) -> Optional[Path]:
        """Build machine settings file including process profile."""
        try:
            # Map printer model to profile name
            profile_name = self.PRINTER_MODEL_MAP.get(printer_model, printer_model)

            # Determine nozzle size suffix
            nozzle_size = nozzle_diameter or 0.4
            nozzle_suffix = f"{nozzle_size} nozzle"

            # Look for machine profile
            machine_file = f"{profile_name}.json"
            machine_nozzle_file = f"{profile_name} {nozzle_suffix}.json"

            machine_settings = {}

            # Try to load base machine profile
            base_machine_path = MACHINE_PROFILES_PATH / machine_file
            if base_machine_path.exists():
                with open(base_machine_path, "r") as f:
                    machine_settings = json.load(f)
                logger.info(f"Loaded base machine profile: {machine_file}")

            # Try to load nozzle-specific machine profile
            nozzle_machine_path = MACHINE_PROFILES_PATH / machine_nozzle_file
            if nozzle_machine_path.exists():
                with open(nozzle_machine_path, "r") as f:
                    nozzle_settings = json.load(f)
                    # Merge nozzle-specific settings
                    machine_settings.update(nozzle_settings)
                logger.info(
                    f"Loaded nozzle-specific machine profile: {machine_nozzle_file}"
                )

            # Load process profile
            process_settings = self._load_process_profile(
                printer_model, nozzle_size, print_quality
            )
            if process_settings:
                # Merge process settings
                machine_settings.update(process_settings)

            # Save combined settings to temp file
            if machine_settings:
                settings_file = (
                    self.temp_dir / f"machine_{printer_model}_{nozzle_size}mm.json"
                )
                with open(settings_file, "w") as f:
                    json.dump(machine_settings, f, indent=2)
                logger.info(f"Generated machine settings: {settings_file}")
                return settings_file

            logger.warning(f"No machine settings found for {printer_model}")
            return None

        except Exception as e:
            logger.error(f"Error building machine settings: {e}")
            return None

    def _load_process_profile(
        self,
        printer_model: str,
        nozzle_size: float,
        print_quality: Optional[str] = None,
    ) -> Optional[Dict]:
        """Load appropriate process (print quality) profile."""
        try:
            # Use provided quality or default based on nozzle size
            if not print_quality:
                print_quality = self.DEFAULT_QUALITY_PROFILES.get(
                    nozzle_size, "0.20mm Standard"
                )

            # Build process profile filename
            # Format: "0.16mm Optimal @BBL X1C.json" or
            # "0.16mm Optimal @BBL X1C 0.4 nozzle.json"
            profile_name = self.PRINTER_MODEL_MAP.get(printer_model, printer_model)

            # Remove "Bambu Lab " prefix for process profiles
            profile_suffix = profile_name.replace("Bambu Lab ", "")

            # Special handling for X1 Carbon -> X1C in process profiles
            if profile_suffix == "X1 Carbon":
                profile_suffix = "X1C"

            # Try with nozzle-specific profile first
            process_file = (
                f"{print_quality} @BBL {profile_suffix} {nozzle_size} nozzle.json"
            )
            process_path = PROCESS_PROFILES_PATH / process_file

            if not process_path.exists():
                # Try without nozzle specification
                process_file = f"{print_quality} @BBL {profile_suffix}.json"
                process_path = PROCESS_PROFILES_PATH / process_file

            if process_path.exists():
                with open(process_path, "r") as f:
                    process_settings = json.load(f)
                logger.info(f"Loaded process profile: {process_file}")
                return process_settings
            else:
                logger.warning(f"Process profile not found: {process_file}")

                # Try generic quality profile
                generic_file = f"{print_quality} @BBL X1C.json"
                generic_path = PROCESS_PROFILES_PATH / generic_file
                if generic_path.exists():
                    with open(generic_path, "r") as f:
                        process_settings = json.load(f)
                    logger.info(f"Loaded generic process profile: {generic_file}")
                    return process_settings

            return None

        except Exception as e:
            logger.error(f"Error loading process profile: {e}")
            return None

    def _build_filament_settings(
        self,
        printer_model: str,
        nozzle_diameter: Optional[float],
        filament_types: List[str],
        filament_colors: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Build filament settings file paths.

        Returns:
            String containing semicolon-separated list of filament file paths
        """
        try:
            filament_paths = []
            nozzle_size = nozzle_diameter or 0.4

            # Remove "Bambu Lab " prefix for filament profiles
            profile_name = self.PRINTER_MODEL_MAP.get(printer_model, printer_model)
            profile_suffix = profile_name.replace("Bambu Lab ", "")

            for idx, filament_type in enumerate(filament_types):
                # Get the color for this filament (if provided)
                filament_color = None
                if filament_colors and idx < len(filament_colors):
                    filament_color = filament_colors[idx]

                # Map filament type to Bambu profile name
                bambu_filament = self.MATERIAL_TYPE_MAP.get(
                    filament_type, f"Bambu {filament_type}"
                )

                # Try different filament profile variations
                base_profile_path = None

                # Try nozzle-specific profile first
                filament_file = (
                    f"{bambu_filament} @BBL {profile_suffix} {nozzle_size} nozzle.json"
                )
                test_path = FILAMENT_PROFILES_PATH / filament_file

                if not test_path.exists():
                    # Try without nozzle
                    filament_file = f"{bambu_filament} @BBL {profile_suffix}.json"
                    test_path = FILAMENT_PROFILES_PATH / filament_file

                if not test_path.exists():
                    # Try base profile
                    filament_file = f"{bambu_filament} @base.json"
                    test_path = FILAMENT_PROFILES_PATH / filament_file

                if not test_path.exists():
                    # Try generic material
                    filament_file = f"Generic {filament_type} @BBL.json"
                    test_path = FILAMENT_PROFILES_PATH / filament_file

                if test_path.exists():
                    base_profile_path = test_path
                    logger.info(f"Found filament profile: {filament_file}")

                # If we have a color and a base profile,
                # create a custom profile with the color
                if filament_color and base_profile_path:
                    try:
                        # Load the base profile
                        with open(base_profile_path, "r") as f:
                            profile_data = json.load(f)

                        # Update the color
                        profile_data["filament_colour"] = [filament_color]

                        # Update the name to indicate it's a custom color variant
                        if "name" in profile_data:
                            profile_data["name"] = (
                                f"{profile_data['name']} (Custom Color)"
                            )

                        # Save to a temporary file
                        temp_file = (
                            self.temp_dir
                            / f"filament_{filament_type}_{idx}_colored.json"
                        )
                        with open(temp_file, "w") as f:
                            json.dump(profile_data, f, indent=2)

                        filament_paths.append(str(temp_file))
                        logger.info(
                            f"Created custom colored filament profile: {temp_file}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to create colored profile, using base: {e}"
                        )
                        filament_paths.append(str(base_profile_path))
                elif base_profile_path:
                    # Use the base profile as-is if no color specified
                    filament_paths.append(str(base_profile_path))
                else:
                    # No profile found, create a minimal one
                    logger.warning(
                        f"No filament profile found for {filament_type} "
                        f"on {printer_model}"
                    )
                    minimal_profile = {
                        "type": "filament",
                        "name": f"Generic {filament_type}",
                        "filament_id": [filament_type],
                        "filament_type": [filament_type],
                        "filament_colour": [
                            filament_color if filament_color else "#00000000"
                        ],
                        "nozzle_temperature": [210 if filament_type == "PLA" else 240],
                        "bed_temperature": [60 if filament_type == "PLA" else 80],
                    }

                    # Save minimal profile
                    temp_file = self.temp_dir / f"filament_{filament_type}_{idx}.json"
                    with open(temp_file, "w") as f:
                        json.dump(minimal_profile, f, indent=2)
                    filament_paths.append(str(temp_file))

            # Return semicolon-separated list
            if filament_paths:
                result = ";".join(filament_paths)
                logger.info(f"Generated filament paths: {result}")
                return result

            return None

        except Exception as e:
            logger.error(f"Error building filament settings: {e}")
            return None

    def cleanup_temp_files(self):
        """Clean up temporary settings files."""
        try:
            for file in self.temp_dir.glob("*.json"):
                file.unlink()
            logger.debug("Cleaned up temporary settings files")
        except Exception as e:
            logger.warning(f"Error cleaning up temp files: {e}")
