"""
LANbu Handy - Backend Main Application

FastAPI application for LANbu Handy - a self-hosted PWA for slicing and
printing 3D models to Bambu Lab printers in LAN-only mode.
"""

import logging

# Configure logging to show INFO level messages
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Disable MQTT debug logging
logging.getLogger("paho.mqtt").setLevel(logging.WARNING)
logging.getLogger("paho.mqtt.client").setLevel(logging.WARNING)
logging.getLogger("paho.mqtt.publish").setLevel(logging.WARNING)

# Disable the v3 patch executor to prevent interference
import sys  # noqa: E402

if "app.mqtt_async_patch_v3" in sys.modules:
    del sys.modules["app.mqtt_async_patch_v3"]
if "app.mqtt_async_patch_v4" in sys.modules:
    del sys.modules["app.mqtt_async_patch_v4"]

# Import and apply async MQTT patch before other imports
# TEMPORARILY USING SIMPLE ASYNC IMPLEMENTATION TO FIX BLOCKING
from app.mqtt_async_simple import (  # noqa: E402
    add_simple_async_support_to_printer_service,
)

add_simple_async_support_to_printer_service()

from pathlib import Path  # noqa: E402,F401

from app.job_orchestration import (  # noqa: E402,F401
    download_model_step,
    slice_model_step,
    start_print_step,
    upload_gcode_step,
)
from app.routers import models, printers, printing, slicing, system  # noqa: E402
from app.schemas import FilamentMapping  # noqa: E402,F401
from app.slicer_service import slice_model  # noqa: E402,F401
from app.utils import (  # noqa: E402,F401
    build_slicing_options_from_config,
    find_gcode_file,
    get_default_slicing_options,
    get_gcode_output_dir,
)
from fastapi import FastAPI  # noqa: E402

logger = logging.getLogger(__name__)

app = FastAPI(
    title="LANbu Handy",
    description="Self-hosted PWA for slicing and printing 3D models to "
    "Bambu Lab printers in LAN-only mode",
    version="0.1.0",
)

# Import config separately to avoid circular dependencies
from app.config import get_config  # noqa: E402,F401

# Import services from services module for consistency
from app.services import (  # noqa: E402,F401
    model_service,
    printer_service,
    slice_progress_service,
    slicer_service,
    thumbnail_service,
    upload_progress_service,
)

config = get_config()

# Import job orchestration functions for backward compatibility
# These functions are used by tests that patch them via app.main.function_name
# (Note: these are already imported at the top but we need them available
# as module attributes)


# Create a mock job orchestrator for backward compatibility with tests
class JobOrchestrator:
    """Mock job orchestrator for backward compatibility with tests."""

    pass


job_orchestrator = JobOrchestrator()

# Add system routes and event handlers
system.add_system_routes_and_handlers(app, printer_service, thumbnail_service)

# Include routers
app.include_router(models.router)
app.include_router(slicing.router)
app.include_router(printers.router)
app.include_router(printing.router)

# TODO: Add WebSocket endpoint for printer status
# @app.websocket("/ws/printer-status")
# async def websocket_printer_status(websocket: WebSocket):
#     pass

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
