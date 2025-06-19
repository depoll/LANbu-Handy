import pytest
from app.slice_progress_service import (
    SliceProgress,
    SliceProgressService,
    SliceProgressSession,
)


class TestSliceProgressService:
    def test_service_initialization(self):
        service = SliceProgressService()
        assert service.sessions == {}
        assert hasattr(service, "cli_wrapper")
        assert hasattr(service, "temp_dir")

    def test_create_session(self):
        service = SliceProgressService()
        file_id = "test-file-123"
        plate_indices = [0, 1, 2]

        session_id = service.create_session(file_id, plate_indices)

        assert session_id in service.sessions
        session = service.sessions[session_id]
        assert session.file_id == file_id
        assert session.plate_indices == plate_indices
        assert session.current_plate_index == 0
        assert len(session.progress_history) == 0
        assert session.is_active is True

    def test_get_session_status_exists(self):
        service = SliceProgressService()
        session_id = service.create_session("test-file", [0, 1])

        status = service.get_session_status(session_id)

        assert status["session_id"] == session_id
        assert status["file_id"] == "test-file"
        assert status["total_plates"] == 2
        assert status["current_plate_index"] == 0
        assert status["is_active"] is True
        assert "created_at" in status

    def test_get_session_status_not_found(self):
        service = SliceProgressService()

        status = service.get_session_status("non-existent")

        assert status["session_id"] == "non-existent"
        assert status["error"] == "Session not found"

    def test_parse_cli_progress_plate_processing(self):
        service = SliceProgressService()

        progress = service._parse_cli_progress("Processing plate 1 of 3", plate_index=0)

        assert progress is not None
        assert progress.phase == "processing_plate"
        assert progress.message == "Processing plate 1 of 3"
        assert progress.plate_index == 0

    def test_parse_cli_progress_with_percentage(self):
        service = SliceProgressService()

        progress = service._parse_cli_progress("Slicing: 45%", plate_index=1)

        assert progress is not None
        assert progress.progress_percent == 45.0
        assert progress.plate_index == 1

    def test_parse_cli_progress_gcode_generation(self):
        service = SliceProgressService()

        progress = service._parse_cli_progress(
            "Generating G-code for plate 2", plate_index=1
        )

        assert progress is not None
        assert progress.phase == "gcode_generation"
        assert progress.plate_index == 1

    def test_parse_cli_progress_invalid_message(self):
        service = SliceProgressService()

        progress = service._parse_cli_progress("Random log message", plate_index=0)

        assert progress is None

    def test_cleanup_session(self):
        service = SliceProgressService()
        session_id = service.create_session("test-file", [0])

        # Verify session exists
        assert session_id in service.sessions

        # Clean up
        service.cleanup_session(session_id)

        # Verify session is removed
        assert session_id not in service.sessions

    def test_cleanup_nonexistent_session(self):
        service = SliceProgressService()

        # Should not raise exception
        service.cleanup_session("non-existent-session")

    @pytest.mark.skip(reason="Async streaming not easily testable in sync context")
    def test_stream_progress_updates(self):
        # This would require async test setup
        pass

    def test_session_data_structure(self):
        session = SliceProgressSession(
            session_id="test-123", file_id="file-456", plate_indices=[0, 1, 2]
        )

        assert session.session_id == "test-123"
        assert session.file_id == "file-456"
        assert session.plate_indices == [0, 1, 2]
        assert session.current_plate_index == 0
        assert session.is_active is True
        assert len(session.progress_history) == 0

    def test_add_progress_to_session(self):
        service = SliceProgressService()
        session_id = service.create_session("test-file", [0])
        session = service.sessions[session_id]

        # Add progress
        progress = SliceProgress(
            timestamp="2024-01-01T00:00:00",
            phase="slicing",
            plate_index=0,
            progress_percent=50.0,
            message="Slicing: 50%",
        )

        session.progress_history.append(progress)

        assert len(session.progress_history) == 1
        assert session.progress_history[0].progress_percent == 50.0

    def test_parse_cli_progress_edge_cases(self):
        service = SliceProgressService()

        # Test various percentage formats
        progress1 = service._parse_cli_progress("Progress: 100%", plate_index=0)
        assert progress1.progress_percent == 100.0

        progress2 = service._parse_cli_progress("0% complete", plate_index=0)
        assert progress2.progress_percent == 0.0

        # Test plate detection
        progress3 = service._parse_cli_progress("Starting plate 0", plate_index=0)
        assert progress3 is not None
        assert progress3.phase == "processing_plate"

    @pytest.mark.skip(reason="Requires actual CLI wrapper implementation")
    def test_run_progressive_slice(self):
        # This would test the actual slicing process
        pass
