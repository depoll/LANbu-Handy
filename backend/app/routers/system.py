"""
System-level endpoints for LANbu Handy
"""

import asyncio
import logging
from pathlib import Path

from app.config import get_config
from app.printer_service import PrinterService
from app.printer_status_monitor import printer_status_monitor
from app.thumbnail_service import ThumbnailService
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

router = APIRouter()

# Path to the PWA static files directory
DOCKER_STATIC_PWA_DIR = Path("/app/static_pwa")
LOCAL_STATIC_PWA_DIR = Path(__file__).resolve().parent.parent.parent / "pwa" / "dist"
STATIC_PWA_DIR = (
    DOCKER_STATIC_PWA_DIR if DOCKER_STATIC_PWA_DIR.exists() else LOCAL_STATIC_PWA_DIR
)


def add_system_routes_and_handlers(
    app: FastAPI, printer_service: PrinterService, thumbnail_service: ThumbnailService
):
    """
    Adds system-level routes, static file mounts, and event handlers to the FastAPI app.
    """
    # Mount static files for PWA assets (CSS, JS, etc.)
    if STATIC_PWA_DIR.exists():
        app.mount(
            "/assets", StaticFiles(directory=STATIC_PWA_DIR / "assets"), name="assets"
        )
        logger.info(f"Mounted PWA assets from: {STATIC_PWA_DIR / 'assets'}")

    # Mount Bambu Studio resources for printer images
    BAMBU_RESOURCES_DIR = Path("/opt/bambu-studio-resources")
    if not BAMBU_RESOURCES_DIR.exists():
        BAMBU_RESOURCES_DIR = (
            Path(__file__).resolve().parent.parent.parent / "bambu-studio-resources"
        )

    if BAMBU_RESOURCES_DIR.exists():
        app.mount(
            "/api/resources",
            StaticFiles(directory=BAMBU_RESOURCES_DIR),
            name="bambu-resources",
        )
        logger.info(f"Mounted Bambu resources from: {BAMBU_RESOURCES_DIR}")

    @app.on_event("startup")
    async def startup_event():
        """Initialize services and clean up old files on startup."""
        logger.info("LANbu Handy backend starting up...")
        try:
            config = get_config()
            app.state.config = config
            printer_status_monitor.set_dependencies(config, printer_service)
            asyncio.create_task(printer_status_monitor.start())
            thumbnail_service.cleanup_old_thumbnails(max_age_hours=24)
            logger.info("Startup complete!")
        except Exception as e:
            logger.error(f"Error during startup: {e}", exc_info=True)
            raise

    @app.on_event("shutdown")
    async def shutdown_event():
        """Clean up resources on shutdown."""
        logger.info("LANbu Handy backend shutting down...")
        await printer_status_monitor.stop()
        logger.info("Printer status monitor stopped")
        thumbnail_service.cleanup_old_thumbnails(max_age_hours=0)
        logger.info("Final cleanup of thumbnail files")

    app.include_router(router)


@router.get("/")
async def serve_pwa():
    """
    Serve the PWA's index.html file for the root path.
    """
    index_path = STATIC_PWA_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    else:
        logger.error(f"PWA index.html not found at: {index_path}")
        return {
            "message": "LANbu Handy",
            "status": "PWA files not found",
            "version": "0.1.0",
        }


@router.get("/api/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy"}


@router.get("/api/status")
async def status():
    """
    Basic backend status endpoint.
    """
    return {"status": "ok", "application_name": "LANbu Handy", "version": "0.0.1"}


@router.get("/api/config")
async def get_app_config(app: FastAPI):
    """
    Get application configuration status.
    """
    config = getattr(app.state, "config", None)
    if config is None:
        raise HTTPException(
            status_code=503, detail="Service starting up, please try again in a moment"
        )

    printers = config.get_printers()
    persistent_printers = config.get_persistent_printers()
    persistent_ips = {p.ip for p in persistent_printers}

    printers_info = [
        {
            "name": p.name,
            "canonical_id": p.canonical_id,
            "ip": p.ip,
            "has_access_code": bool(p.access_code),
            "has_serial_number": bool(p.serial_number),
            "is_persistent": p.ip in persistent_ips,
            "source": "persistent" if p.ip in persistent_ips else "environment",
        }
        for p in printers
    ]

    active_printer = config.get_active_printer()
    active_printer_info = None
    if active_printer:
        is_persistent = active_printer.ip in persistent_ips
        active_printer_info = {
            "name": active_printer.name,
            "canonical_id": active_printer.canonical_id,
            "ip": active_printer.ip,
            "has_access_code": bool(active_printer.access_code),
            "has_serial_number": bool(active_printer.serial_number),
            "is_runtime_set": True,
            "is_persistent": is_persistent,
        }

    return {
        "printer_configured": config.is_printer_configured(),
        "printers": printers_info,
        "printer_count": len(printers),
        "persistent_printer_count": len(persistent_printers),
        "active_printer": active_printer_info,
        "printer_ip": (
            config.get_printer_ip() if config.is_printer_configured() else None
        ),
    }
