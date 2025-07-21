"""
Shared schemas and exceptions for printer communication services.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


# --- Custom Exceptions ---


class PrinterCommunicationError(Exception):
    """Base exception for printer communication errors."""

    pass


class PrinterConnectionError(PrinterCommunicationError):
    """Exception raised when unable to connect to the printer."""

    pass


class PrinterAuthenticationError(PrinterCommunicationError):
    """Exception raised when authentication fails."""

    pass


class PrinterFileTransferError(PrinterCommunicationError):
    """Exception raised when a file transfer fails."""

    pass


class PrinterMQTTError(PrinterCommunicationError):
    """Exception raised for MQTT communication failures."""

    pass


# --- Result Dataclasses ---


@dataclass
class FTPUploadResult:
    """Result of an FTP upload operation."""

    success: bool
    message: str
    remote_path: Optional[str] = None
    error_details: Optional[str] = None


@dataclass
class MQTTResult:
    """Result of an MQTT operation."""

    success: bool
    message: str
    error_details: Optional[str] = None


# --- Data Model Dataclasses ---


@dataclass
class AMSFilament:
    """Information about a filament in an AMS slot."""

    slot_id: int
    filament_type: str
    color: str
    material_id: Optional[str] = None


@dataclass
class ExternalSpool:
    """Information about the external spool (virtual tray)."""

    slot_id: int = 254
    filament_type: str = "Unknown"
    color: str = "#00000000"
    material_id: Optional[str] = None
    available: bool = False


@dataclass
class AMSUnit:
    """Information about an AMS unit."""

    unit_id: int
    filaments: List[AMSFilament]


@dataclass
class PrinterStatusResult:
    """Result of a printer status query including model info."""

    success: bool
    message: str
    printer_model: Optional[str] = None
    printer_name: Optional[str] = None
    ams_units: List[AMSUnit] = field(default_factory=list)
    external_spool: Optional[ExternalSpool] = None
    nozzle_diameter: Optional[float] = None
    error_details: Optional[str] = None
    raw_data: Optional[dict] = None


@dataclass
class AMSStatusResult:
    """Result of an AMS status query."""

    success: bool
    message: str
    ams_units: List[AMSUnit] = field(default_factory=list)
    external_spool: Optional[ExternalSpool] = None
    error_details: Optional[str] = None
    raw_data: Optional[dict] = None
