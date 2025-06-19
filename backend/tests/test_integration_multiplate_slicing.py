import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from app.main import app
from app.slice_progress_service import SliceProgressService
from fastapi.testclient import TestClient


class TestMultiplateSlicingIntegration:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def test_3mf_file(self):
        """Create a test 3MF file for upload"""
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as tmp:
            # Write minimal 3MF content
            import zipfile

            with zipfile.ZipFile(tmp.name, "w") as zf:
                # Add model file
                zf.writestr("3D/3dmodel.model", '<?xml version="1.0"?><model/>')
                # Add config with multiplate
                config = {
                    "print": {
                        "filament_type": ["PLA", "PETG"],
                        "filament_color": ["#FF0000", "#00FF00"],
                    },
                    "plates": [
                        {"name": "Plate 1", "objects": [1, 2]},
                        {"name": "Plate 2", "objects": [3, 4]},
                    ],
                }
                zf.writestr("Metadata/plate_1.json", json.dumps(config))

            yield tmp.name

        # Cleanup
        os.unlink(tmp.name)

    @pytest.mark.skip(reason="Endpoint not implemented yet")
    @pytest.mark.asyncio
    async def test_complete_multiplate_slice_workflow(self, client, test_3mf_file):
        # Step 1: Upload model file
        with open(test_3mf_file, "rb") as f:
            response = client.post(
                "/api/model/upload-file",
                files={"file": ("test_model.3mf", f, "application/octet-stream")},
            )

        assert response.status_code == 200
        upload_data = response.json()
        file_id = upload_data["file_id"]
        assert upload_data["success"] is True
        assert upload_data["plates"] is not None
        assert len(upload_data["plates"]) >= 1

        # Step 2: Configure printer
        with patch("app.main.config") as mock_config:
            mock_printer = Mock(
                name="Test Printer", ip="192.168.1.100", access_code="12345678"
            )
            mock_config.get_printer_by_name.return_value = mock_printer

            # Step 3: Start progressive slicing
            with patch("app.main.slice_progress_service") as mock_progress_service:
                mock_progress_service.create_session.return_value = "session-123"

                slice_request = {
                    "file_id": file_id,
                    "filament_mappings": [
                        {"filament_index": 0, "ams_unit_id": 0, "ams_slot_id": 0},
                        {"filament_index": 1, "ams_unit_id": 0, "ams_slot_id": 1},
                    ],
                    "build_plate_type": "textured_plate",
                    "plate_selection": [0, 1],
                }

                response = client.post("/api/slice/start-progress", json=slice_request)

                assert response.status_code == 200
                start_data = response.json()
                assert start_data["success"] is True
                assert start_data["session_id"] == "session-123"

        # Step 4: Stream progress updates
        # Note: Can't easily test SSE in sync tests, but we can test the endpoint exists
        response = client.get("/api/slice/progress/session-123/stream")
        # SSE endpoint returns a StreamingResponse, which is hard to test synchronously

        # Step 5: Verify configured slice works for individual plates
        with patch("app.main.slicer_service") as mock_slicer:
            mock_slicer.slice_model.return_value = {
                "success": True,
                "gcode_path": "/tmp/plate_0.gcode",
                "print_time": "2h 30m",
                "filament_usage": 15.5,
                "first_layer_time": "3m 20s",
            }

            response = client.post(
                "/api/slice/configured",
                json={
                    "file_id": file_id,
                    "filament_mappings": slice_request["filament_mappings"],
                    "build_plate_type": "textured_plate",
                    "plate_selection": 0,  # Single plate
                },
            )

            assert response.status_code == 200
            slice_data = response.json()
            assert slice_data["success"] is True
            assert slice_data["gcode_path"] is not None

    @pytest.mark.skip(reason="Model service mocking not working correctly")
    def test_multiplate_slice_with_stl_conversion(self, client):
        """Test slicing workflow with STL to 3MF conversion"""
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as stl_file:
            # Write minimal STL content
            stl_file.write(b"solid test\nendsolid test\n")
            stl_file.flush()

            try:
                # Upload STL file
                with open(stl_file.name, "rb") as f:
                    with patch("app.main.model_service") as mock_model_service:
                        # Mock STL to 3MF conversion
                        mock_model_service.save_uploaded_file.return_value = {
                            "success": True,
                            "file_id": "stl-converted-123",
                            "file_name": "test_model.stl",
                            "file_path": "/tmp/test_model.stl",
                            "preview_type": "stl",
                            "plates": [
                                {"plate_id": 1, "plate_index": 0, "name": "Plate 1"}
                            ],
                        }

                        response = client.post(
                            "/api/model/upload-file",
                            files={
                                "file": (
                                    "test_model.stl",
                                    f,
                                    "application/octet-stream",
                                )
                            },
                        )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "file_id" in data
                assert len(data.get("plates", [])) >= 1

            finally:
                os.unlink(stl_file.name)

    @pytest.mark.skip(reason="Endpoint not implemented yet")
    def test_multiplate_progressive_slice_error_handling(self, client):
        """Test error handling in progressive slicing"""
        with patch("app.main.slice_progress_service") as mock_progress_service:
            mock_progress_service.create_session.return_value = "error-session"

            # Test with invalid file ID
            response = client.post(
                "/api/slice/start-progress",
                json={
                    "file_id": "non-existent-file",
                    "filament_mappings": [],
                    "build_plate_type": "textured_plate",
                    "plate_selection": [0],
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "not found" in data["error"].lower()

    def test_slice_progress_streaming_session_management(self, client):
        """Test SSE streaming and session management"""
        service = SliceProgressService()

        # Create a session
        session_id = service.create_session(
            file_id="test-file", plate_indices=[0, 1, 2]
        )
        assert session_id in service.sessions

        # Test progress parsing
        progress1 = service._parse_cli_progress("Processing plate 1...", plate_index=0)
        assert progress1 is not None
        assert progress1.phase == "processing_plate"

        progress2 = service._parse_cli_progress("Slicing: 50%", plate_index=0)
        assert progress2.progress_percent == 50.0

        # Get session status
        status = service.get_session_status(session_id)
        assert status["total_plates"] == 3
        assert status["is_active"] is True

        # Clean up
        service.cleanup_session(session_id)
        assert session_id not in service.sessions

    @pytest.mark.skip(reason="Slicer service not available in main module")
    @pytest.mark.asyncio
    async def test_parallel_plate_slicing(self, client):
        """Test that multiple plates can be sliced in parallel"""
        with patch("app.main.slicer_service") as mock_slicer:
            # Mock different slice times for different plates
            async def mock_slice(file_path, options):
                plate_num = int(options.get("plate_selection", 0))
                await asyncio.sleep(
                    0.1 * (plate_num + 1)
                )  # Simulate varying slice times
                return {
                    "success": True,
                    "gcode_path": f"/tmp/plate_{plate_num}.gcode",
                    "print_time": f"{plate_num + 1}h",
                    "filament_usage": 10.0 * (plate_num + 1),
                }

            mock_slicer.slice_model = AsyncMock(side_effect=mock_slice)

            # Test slicing multiple plates
            tasks = []
            for plate_idx in range(3):
                response = client.post(
                    "/api/slice/configured",
                    json={
                        "file_id": "test-file",
                        "filament_mappings": [
                            {"filament_index": 0, "ams_unit_id": 0, "ams_slot_id": 0}
                        ],
                        "build_plate_type": "textured_plate",
                        "plate_selection": plate_idx,
                    },
                )
                tasks.append(response)

            # All requests should complete
            for i, response in enumerate(tasks):
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert f"plate_{i}.gcode" in data["gcode_path"]

    @pytest.mark.skip(reason="Endpoint not implemented yet")
    def test_plate_specific_filament_requirements(self, client):
        """Test that filament requirements are correctly filtered per plate"""
        with patch("app.main.model_service") as mock_model_service:
            # Mock model with different filament requirements per plate
            mock_model_service.get_file_info.return_value = {
                "file_id": "multi-filament-123",
                "file_name": "multi_filament.3mf",
                "file_path": "/tmp/multi_filament.3mf",
                "plates": [
                    {
                        "plate_id": 1,
                        "plate_index": 0,
                        "name": "Plate 1",
                        "filament_requirements": {
                            "filament_count": 2,
                            "filament_types": ["PLA", "PLA"],
                            "filament_colors": ["#FF0000", "#00FF00"],
                        },
                    },
                    {
                        "plate_id": 2,
                        "plate_index": 1,
                        "name": "Plate 2",
                        "filament_requirements": {
                            "filament_count": 1,
                            "filament_types": ["PETG"],
                            "filament_colors": ["#0000FF"],
                        },
                    },
                ],
            }

            # Get requirements for plate 1
            response = client.get(
                "/api/model/multi-filament-123/plate/0/filament-requirements"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["filament_count"] == 2
            assert data["filament_types"] == ["PLA", "PLA"]

            # Get requirements for plate 2
            response = client.get(
                "/api/model/multi-filament-123/plate/1/filament-requirements"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["filament_count"] == 1
            assert data["filament_types"] == ["PETG"]

    @pytest.mark.skip(reason="Endpoint not implemented yet")
    def test_plate_thumbnail_generation(self, client):
        """Test plate-specific thumbnail generation"""
        with patch("app.main.model_service") as mock_model_service:
            mock_model_service.get_file_info.return_value = {
                "file_id": "thumb-test",
                "file_path": "/tmp/thumb_test.3mf",
                "plates": [
                    {"plate_index": 0, "thumbnail": "plate0_thumb.png"},
                    {"plate_index": 1, "thumbnail": "plate1_thumb.png"},
                ],
            }

            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data=b"PNG_DATA")):
                    # Get thumbnail for plate 0
                    response = client.get("/api/model/thumbnail/thumb-test/plate/0")
                    assert response.status_code == 200
                    assert response.headers["content-type"] == "image/png"

    @pytest.mark.skip(reason="Job orchestrator not available in main module")
    def test_end_to_end_print_workflow(self, client):
        """Test complete workflow from upload to print"""
        # Step 1: Configure printer
        with patch("app.main.config") as mock_config:
            mock_printer = Mock(
                name="Test Printer", ip="192.168.1.100", access_code="12345678"
            )
            mock_config.printers = [mock_printer]
            mock_config.active_printer = mock_printer

            # Step 2: Mock complete workflow
            with patch("app.main.job_orchestrator") as mock_orchestrator:
                mock_orchestrator.execute_job = AsyncMock(
                    return_value={
                        "success": True,
                        "job_id": "print-job-123",
                        "steps": [
                            {"step": "download", "success": True},
                            {"step": "slice", "success": True},
                            {"step": "upload", "success": True},
                            {"step": "start_print", "success": True},
                        ],
                    }
                )

                response = client.post(
                    "/api/job/start",
                    json={
                        "model_url": "https://example.com/model.3mf",
                        "filament_mappings": [
                            {"filament_index": 0, "ams_unit_id": 0, "ams_slot_id": 0}
                        ],
                        "build_plate_type": "textured_plate",
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["job_id"] == "print-job-123"


def mock_open(read_data=None):
    """Helper to mock file open"""
    m = MagicMock()
    m.read.return_value = read_data
    m.__enter__.return_value = m
    return MagicMock(return_value=m)
