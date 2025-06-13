"""
LANbu Handy - Slice Progress Service

This module provides real-time progress tracking for slicing operations
using named pipes and the Bambu Studio CLI --pipe option.
"""

import asyncio
import logging
import os
import tempfile
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import AsyncGenerator, Callable, Dict, List, Optional, Union

from .slicer_service import BambuStudioCLIWrapper, CLIResult

logger = logging.getLogger(__name__)


@dataclass
class SliceProgress:
    """Progress information for a slicing operation."""

    plate_index: Optional[int]
    phase: str
    progress_percent: float
    message: str
    timestamp: float
    is_complete: bool = False

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class SliceProgressSession:
    """Session information for a slice progress tracking operation."""

    session_id: str
    file_id: str
    plate_indices: List[int]
    current_plate: Optional[int] = None
    completed_plates: List[int] = None
    is_active: bool = True
    start_time: float = None

    def __post_init__(self):
        if self.completed_plates is None:
            self.completed_plates = []
        if self.start_time is None:
            self.start_time = time.time()


class SliceProgressService:
    """
    Service for tracking real-time slicing progress using named pipes.

    This service creates named pipes for each slicing operation and monitors
    them for progress updates from the Bambu Studio CLI.
    """

    def __init__(self):
        self.sessions: Dict[str, SliceProgressSession] = {}
        self.active_pipes: Dict[str, Path] = {}
        self.cli_wrapper = BambuStudioCLIWrapper()
        self.temp_dir = Path(tempfile.gettempdir()) / "lanbu-handy-pipes"
        self.temp_dir.mkdir(exist_ok=True)

    def create_session(self, file_id: str, plate_indices: List[int]) -> str:
        """
        Create a new slice progress session.

        Args:
            file_id: The file being sliced
            plate_indices: List of plate indices to slice

        Returns:
            Session ID for tracking progress
        """
        session_id = str(uuid.uuid4())
        session = SliceProgressSession(
            session_id=session_id, file_id=file_id, plate_indices=plate_indices.copy()
        )
        self.sessions[session_id] = session
        logger.info(
            f"Created slice progress session {session_id} for file {file_id} "
            f"with plates {plate_indices}"
        )
        return session_id

    def _create_named_pipe(
        self, session_id: str, plate_index: Optional[int] = None
    ) -> Path:
        """
        Create a named pipe for progress tracking.

        Args:
            session_id: The session ID
            plate_index: Optional plate index for plate-specific pipes

        Returns:
            Path to the created named pipe
        """
        if plate_index is not None:
            pipe_name = f"slice_progress_{session_id}_plate_{plate_index}"
        else:
            pipe_name = f"slice_progress_{session_id}"

        pipe_path = self.temp_dir / pipe_name

        # Remove existing pipe if it exists
        if pipe_path.exists():
            pipe_path.unlink()

        # Create named pipe
        try:
            os.mkfifo(str(pipe_path))
            logger.debug(f"Created named pipe: {pipe_path}")
            return pipe_path
        except OSError as e:
            logger.error(f"Failed to create named pipe {pipe_path}: {e}")
            raise

    def _read_pipe_progress(
        self,
        pipe_path: Path,
        session_id: str,
        plate_index: Optional[int],
        progress_callback: Callable[[SliceProgress], None],
    ) -> None:
        """
        Read progress updates from a named pipe in a separate thread.

        Args:
            pipe_path: Path to the named pipe
            session_id: Session ID for this operation
            plate_index: Plate index being processed
            progress_callback: Callback to handle progress updates
        """
        logger.debug(f"Starting pipe reader for {pipe_path}")

        try:
            with open(pipe_path, "r") as pipe:
                while True:
                    line = pipe.readline()
                    if not line:
                        break

                    line = line.strip()
                    if not line:
                        continue

                    # Parse progress from CLI output
                    progress = self._parse_cli_progress(line, plate_index)
                    if progress:
                        progress_callback(progress)

        except Exception as e:
            logger.error(f"Error reading from pipe {pipe_path}: {e}")
        finally:
            # Clean up the pipe
            try:
                if pipe_path.exists():
                    pipe_path.unlink()
                    logger.debug(f"Cleaned up pipe: {pipe_path}")
            except Exception as e:
                logger.error(f"Error cleaning up pipe {pipe_path}: {e}")

    def _parse_cli_progress(
        self, line: str, plate_index: Optional[int]
    ) -> Optional[SliceProgress]:
        """
        Parse CLI output line into progress information.

        Args:
            line: Line of output from CLI
            plate_index: Current plate being processed

        Returns:
            SliceProgress object or None if line doesn't contain progress info
        """
        # The CLI outputs progress in various formats. We need to parse these.
        # Common patterns include:
        # - "Processing plate 1..."
        # - "Slicing: 45%"
        # - "Generating support: 23%"
        # - "Writing G-code..."

        timestamp = time.time()

        # Try to extract percentage
        progress_percent = 0.0
        if "%" in line:
            try:
                # Find the percentage value
                import re

                match = re.search(r"(\d+(?:\.\d+)?)%", line)
                if match:
                    progress_percent = float(match.group(1))
            except (ValueError, AttributeError):
                pass

        # Determine phase and message from line content
        line_lower = line.lower()

        if "processing plate" in line_lower:
            phase = "processing_plate"
            message = line
        elif "slicing" in line_lower:
            phase = "slicing"
            message = line
        elif "support" in line_lower:
            phase = "generating_support"
            message = line
        elif "g-code" in line_lower or "gcode" in line_lower:
            phase = "generating_gcode"
            message = line
        elif "complete" in line_lower or "finished" in line_lower:
            phase = "complete"
            message = line
            progress_percent = 100.0
        else:
            phase = "processing"
            message = line

        return SliceProgress(
            plate_index=plate_index,
            phase=phase,
            progress_percent=progress_percent,
            message=message,
            timestamp=timestamp,
            is_complete=(progress_percent >= 100.0 or "complete" in line_lower),
        )

    async def slice_with_progress(
        self,
        session_id: str,
        input_path: Union[str, Path],
        output_dir: Union[str, Path],
        options: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable[[SliceProgress], None]] = None,
    ) -> CLIResult:
        """
        Slice a model with real-time progress tracking.

        Args:
            session_id: Session ID for progress tracking
            input_path: Path to input model file
            output_dir: Output directory for G-code
            options: Optional CLI options
            progress_callback: Optional callback for progress updates

        Returns:
            CLIResult with slicing results
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"No session found for ID: {session_id}")

        input_path = Path(input_path)
        output_dir = Path(output_dir)

        logger.info(f"Starting slice with progress for session {session_id}")

        results = []

        for plate_index in session.plate_indices:
            logger.info(f"Slicing plate {plate_index} for session {session_id}")

            # Update session state
            session.current_plate = plate_index

            # Create named pipe for this plate
            pipe_path = self._create_named_pipe(session_id, plate_index)

            # Set up progress tracking
            def plate_progress_callback(progress: SliceProgress):
                if progress_callback:
                    progress_callback(progress)

            # Start pipe reader in background thread
            pipe_thread = threading.Thread(
                target=self._read_pipe_progress,
                args=(pipe_path, session_id, plate_index, plate_progress_callback),
                daemon=True,
            )
            pipe_thread.start()

            # Build CLI options with pipe
            slice_options = options.copy() if options else {}
            slice_options["pipe"] = str(pipe_path)

            # Create plate-specific output directory
            plate_output_dir = output_dir / f"plate_{plate_index}"
            plate_output_dir.mkdir(parents=True, exist_ok=True)

            # Execute slice command
            result = self.cli_wrapper.slice_model(
                input_path=input_path,
                output_dir=plate_output_dir,
                options=slice_options,
                plate_index=plate_index,
            )

            results.append(result)

            # Mark plate as completed
            if result.success:
                session.completed_plates.append(plate_index)

                # Send completion progress
                completion_progress = SliceProgress(
                    plate_index=plate_index,
                    phase="complete",
                    progress_percent=100.0,
                    message=f"Plate {plate_index} slicing completed successfully",
                    timestamp=time.time(),
                    is_complete=True,
                )
                if progress_callback:
                    progress_callback(completion_progress)
            else:
                # Send failure progress
                failure_progress = SliceProgress(
                    plate_index=plate_index,
                    phase="error",
                    progress_percent=0.0,
                    message=f"Plate {plate_index} slicing failed: {result.stderr}",
                    timestamp=time.time(),
                    is_complete=True,
                )
                if progress_callback:
                    progress_callback(failure_progress)

                # Stop processing on failure
                break

            # Wait for pipe reader to finish
            pipe_thread.join(timeout=5.0)

        # Mark session as complete
        session.is_active = False
        session.current_plate = None

        # Return combined result
        if all(r.success for r in results):
            return CLIResult(
                exit_code=0,
                stdout="\n".join(r.stdout for r in results),
                stderr="",
                success=True,
            )
        else:
            failed_results = [r for r in results if not r.success]
            return CLIResult(
                exit_code=failed_results[0].exit_code,
                stdout="\n".join(r.stdout for r in results),
                stderr="\n".join(r.stderr for r in failed_results),
                success=False,
            )

    async def get_progress_stream(
        self, session_id: str
    ) -> AsyncGenerator[SliceProgress, None]:
        """
        Get an async generator that yields progress updates for a session.

        Args:
            session_id: Session ID to track

        Yields:
            SliceProgress objects as they become available
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"No session found for ID: {session_id}")

        progress_queue = asyncio.Queue()

        def progress_callback(progress: SliceProgress):
            try:
                # Put progress in queue (this is thread-safe)
                asyncio.create_task(progress_queue.put(progress))
            except Exception as e:
                logger.error(f"Error queuing progress update: {e}")

        # This method should be called externally with proper parameters
        # For now, just yield a placeholder message
        yield SliceProgress(
            plate_index=None,
            phase="waiting",
            progress_percent=0.0,
            message="Waiting for slice operation to start...",
            timestamp=time.time(),
            is_complete=False,
        )

        try:
            while session.is_active:
                try:
                    # Wait for progress update with timeout
                    progress = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                    yield progress

                    if (
                        progress.is_complete
                        and progress.plate_index == session.plate_indices[-1]
                    ):
                        # Last plate completed
                        break

                except asyncio.TimeoutError:
                    # Continue waiting
                    continue

        finally:
            # Clean up
            pass

    def get_session_status(self, session_id: str) -> Optional[Dict]:
        """
        Get the current status of a slicing session.

        Args:
            session_id: Session ID to check

        Returns:
            Dictionary with session status or None if not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "file_id": session.file_id,
            "total_plates": len(session.plate_indices),
            "completed_plates": len(session.completed_plates),
            "current_plate": session.current_plate,
            "is_active": session.is_active,
            "start_time": session.start_time,
            "elapsed_time": time.time() - session.start_time,
        }

    def cleanup_session(self, session_id: str) -> None:
        """
        Clean up a completed or failed session.

        Args:
            session_id: Session ID to clean up
        """
        if session_id in self.sessions:
            del self.sessions[session_id]

        # Clean up any remaining pipes
        for pipe_path in self.temp_dir.glob(f"slice_progress_{session_id}*"):
            try:
                pipe_path.unlink()
                logger.debug(f"Cleaned up pipe: {pipe_path}")
            except Exception as e:
                logger.error(f"Error cleaning up pipe {pipe_path}: {e}")


# Global service instance
slice_progress_service = SliceProgressService()
