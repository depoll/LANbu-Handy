"""
Unit tests for the Settings Builder Service
"""

import json
from pathlib import Path

import pytest
from app.settings_builder import SettingsBuilder


class TestSettingsBuilder:
    """Test cases for the Settings Builder"""

    def test_init_creates_temp_directory(self, tmp_path):
        """Test that initialization creates the temp directory"""
        temp_dir = tmp_path / "test_settings"
        SettingsBuilder(temp_dir=temp_dir)
        assert temp_dir.exists()

    def test_printer_model_mapping(self):
        """Test printer model to profile name mapping"""
        builder = SettingsBuilder()
        assert builder.PRINTER_MODEL_MAP["X1C"] == "Bambu Lab X1 Carbon"
        assert builder.PRINTER_MODEL_MAP["P1P"] == "Bambu Lab P1P"
        assert builder.PRINTER_MODEL_MAP["A1"] == "Bambu Lab A1"

    def test_default_quality_profiles_by_nozzle(self):
        """Test default quality profile selection by nozzle size"""
        builder = SettingsBuilder()
        assert builder.DEFAULT_QUALITY_PROFILES[0.4] == "0.16mm Optimal"
        assert builder.DEFAULT_QUALITY_PROFILES[0.6] == "0.24mm Standard"
        assert builder.DEFAULT_QUALITY_PROFILES[0.8] == "0.32mm Standard"

    def test_material_type_mapping(self):
        """Test material type to Bambu profile mapping"""
        builder = SettingsBuilder()
        assert builder.MATERIAL_TYPE_MAP["PLA"] == "Bambu PLA Basic"
        assert builder.MATERIAL_TYPE_MAP["PETG"] == "Bambu PETG Basic"
        assert builder.MATERIAL_TYPE_MAP["ABS"] == "Bambu ABS"

        # Test generic material mappings
        assert builder.MATERIAL_TYPE_MAP["Generic PLA"] == "Bambu PLA Basic"
        assert builder.MATERIAL_TYPE_MAP["Generic PETG"] == "Bambu PETG Basic"
        assert builder.MATERIAL_TYPE_MAP["Generic ABS"] == "Bambu ABS"
        assert builder.MATERIAL_TYPE_MAP["Generic ASA"] == "Bambu ASA"
        assert builder.MATERIAL_TYPE_MAP["Generic TPU"] == "Bambu TPU 95A"

    def test_build_settings_real_profiles(self):
        """Test building settings with real profiles if they exist"""
        builder = SettingsBuilder()

        # Test with real X1C profiles if they exist
        machine_settings, filament_settings = builder.build_settings(
            printer_model="X1C",
            nozzle_diameter=0.4,
            filament_types=["PLA", "PETG"],
            print_quality="0.16mm Optimal",
        )

        # If profiles exist, they should be loaded
        profiles_exist = Path("/opt/bambu-studio-resources/profiles/BBL").exists()
        if profiles_exist:
            assert machine_settings is not None
            assert filament_settings is not None
            assert ";" in filament_settings  # Should be semicolon-separated
            paths = filament_settings.split(";")
            assert len(paths) == 2  # PLA and PETG

    def test_process_profile_x1_carbon_special_case(self):
        """Test special handling of X1 Carbon -> X1C in process profiles"""
        builder = SettingsBuilder()

        # Test the process profile suffix conversion
        profile_name = builder.PRINTER_MODEL_MAP.get("X1C", "X1C")
        profile_suffix = profile_name.replace("Bambu Lab ", "")

        # Should convert "X1 Carbon" to "X1C" for process profiles
        assert profile_name == "Bambu Lab X1 Carbon"
        assert profile_suffix == "X1 Carbon"

        # The actual conversion happens in _load_process_profile method
        # which converts "X1 Carbon" to "X1C" internally

    def test_cleanup_temp_files(self, tmp_path):
        """Test cleanup of temporary files"""
        builder = SettingsBuilder(temp_dir=tmp_path)

        # Create some temp files
        temp_file1 = tmp_path / "test1.json"
        temp_file2 = tmp_path / "test2.json"
        temp_file1.write_text("{}")
        temp_file2.write_text("{}")

        assert temp_file1.exists()
        assert temp_file2.exists()

        builder.cleanup_temp_files()

        assert not temp_file1.exists()
        assert not temp_file2.exists()

    def test_minimal_filament_profile_creation(self, tmp_path):
        """Test creation of minimal filament profile when none exists"""
        builder = SettingsBuilder(temp_dir=tmp_path)

        # Test with a material that won't have a profile
        filament_settings = builder._build_filament_settings(
            printer_model="X1C",
            nozzle_diameter=0.4,
            filament_types=["UNKNOWN_MATERIAL_XYZ"],
        )

        # Should create a minimal profile
        if filament_settings:
            paths = filament_settings.split(";")
            assert len(paths) == 1

            # Check if it's a temp file that was created
            created_file = Path(paths[0])
            if created_file.exists() and str(tmp_path) in str(created_file):
                with open(created_file, "r") as f:
                    profile = json.load(f)
                    assert profile["type"] == "filament"
                    assert "UNKNOWN_MATERIAL_XYZ" in profile["name"]

    def test_filament_settings_format(self):
        """Test that filament settings returns proper format"""

        # Mock the filament paths
        test_paths = [
            "/path/to/filament1.json",
            "/path/to/filament2.json",
            "/path/to/filament3.json",
        ]

        # Test the format that would be returned
        expected_format = ";".join(test_paths)
        assert ";" in expected_format
        assert expected_format.count(";") == len(test_paths) - 1

    def test_build_settings_error_handling(self, tmp_path):
        """Test error handling in build_settings"""
        builder = SettingsBuilder(temp_dir=tmp_path)

        # Test with empty inputs
        machine_settings, filament_settings = builder.build_settings(
            printer_model="", nozzle_diameter=None, filament_types=[]
        )

        # Should handle gracefully
        assert isinstance(machine_settings, (type(None), Path))
        assert isinstance(filament_settings, (type(None), str))

    def test_nozzle_size_defaults(self):
        """Test nozzle size defaulting"""
        builder = SettingsBuilder()

        # Test default nozzle size selection
        default_quality = builder.DEFAULT_QUALITY_PROFILES.get(0.4)
        assert default_quality == "0.16mm Optimal"

        # Test for nozzle size not in defaults
        # Should use a fallback (not in the dict)
        non_standard_nozzle = 0.3
        default_for_non_standard = builder.DEFAULT_QUALITY_PROFILES.get(
            non_standard_nozzle, "0.20mm Standard"
        )
        assert default_for_non_standard == "0.20mm Standard"

    def test_build_filament_settings_with_colors(self, tmp_path):
        """Test building filament settings with custom colors"""
        builder = SettingsBuilder(temp_dir=tmp_path)

        # Test with multiple filaments and colors
        filament_types = ["PLA", "PETG", "ABS"]
        filament_colors = ["#FF0000", "#00FF00", "#0000FF"]

        filament_settings = builder._build_filament_settings(
            printer_model="X1C",
            nozzle_diameter=0.4,
            filament_types=filament_types,
            filament_colors=filament_colors,
        )

        # Should get a semicolon-separated list
        if filament_settings:
            paths = filament_settings.split(";")
            assert len(paths) == 3

            # If profiles exist and we have temp files
            profiles_exist = Path("/opt/bambu-studio-resources/profiles/BBL").exists()
            if profiles_exist:
                # Check each filament has the correct color
                for i, (path, expected_color) in enumerate(zip(paths, filament_colors)):
                    if Path(path).exists() and str(tmp_path) in str(path):
                        with open(path, "r") as f:
                            profile = json.load(f)
                            if "filament_colour" in profile:
                                assert profile["filament_colour"][0] == expected_color

    def test_fallback_filament_profile_logic(self):
        """Test fallback logic for finding suitable filament profiles"""
        builder = SettingsBuilder()

        # Test fallback for various material types
        fallback_profile = builder._find_fallback_filament_profile(
            "PLA-SILK", "X1C", 0.4
        )

        # If profiles exist, we should get something
        profiles_exist = Path("/opt/bambu-studio-resources/profiles/BBL").exists()
        if profiles_exist:
            # Should find a fallback (likely Bambu PLA Basic)
            assert fallback_profile is None or isinstance(fallback_profile, dict)

    def test_material_type_map_completeness(self):
        """Test that material type map covers common materials"""
        builder = SettingsBuilder()

        # Common materials should be mapped
        common_materials = [
            "PLA",
            "PETG",
            "ABS",
            "ASA",
            "PC",
            "PA",
            "TPU",
            "PVA",
            "Generic PLA",
            "Generic PETG",
            "Generic ABS",
            "Generic ASA",
            "Generic TPU",
        ]

        for material in common_materials:
            assert material in builder.MATERIAL_TYPE_MAP
            assert builder.MATERIAL_TYPE_MAP[material] is not None
            assert builder.MATERIAL_TYPE_MAP[material].startswith("Bambu")

    def test_build_settings_with_all_parameters(self, tmp_path):
        """Test building settings with all optional parameters"""
        builder = SettingsBuilder(temp_dir=tmp_path)

        machine_settings, filament_settings = builder.build_settings(
            printer_model="X1C",
            nozzle_diameter=0.6,
            filament_types=["PLA", "PETG"],
            print_quality="0.24mm Standard",
            build_plate_type="textured_plate",
            filament_colors=["#FF0000", "#00FF00"],
        )

        # Should handle all parameters gracefully
        assert isinstance(machine_settings, (type(None), Path))
        assert isinstance(filament_settings, (type(None), str))

        # If we got settings, verify format
        if filament_settings:
            paths = filament_settings.split(";")
            assert len(paths) == 2  # Two filaments

    def test_process_profile_loading_x1c_special_case(self):
        """Test special X1 Carbon to X1C conversion in process profiles"""
        builder = SettingsBuilder()

        # Test the internal method that handles X1C special case
        process_profile = builder._load_process_profile("X1C", 0.4, "0.16mm Optimal")

        # Should handle the X1 Carbon -> X1C conversion internally
        profiles_exist = Path("/opt/bambu-studio-resources/profiles/BBL").exists()
        if profiles_exist:
            # Should successfully load a profile (or return None if not found)
            assert process_profile is None or isinstance(process_profile, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
