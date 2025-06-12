"""
Persistent storage service for printer configurations.

Handles saving and loading printer configurations to/from a JSON file that can be
mounted as a volume for persistence across container upgrades.
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Optional

from app.config import PrinterConfig

logger = logging.getLogger(__name__)


class PrinterStorageError(Exception):
    """Base exception for printer storage errors."""

    pass


class PrinterStorage:
    """Service for persistent printer configuration storage."""

    def __init__(self, config_file_path: Optional[str] = None):
        """Initialize the printer storage service.

        Args:
            config_file_path: Path to the printer config file. If None, uses
                              environment variable or default location.
        """
        if config_file_path:
            self.config_file = Path(config_file_path)
        else:
            # Check for environment variable first, then determine appropriate default
            config_path = os.getenv("PRINTER_CONFIG_FILE")
            if config_path:
                self.config_file = Path(config_path)
            else:
                # Auto-detect appropriate default path based on environment
                self.config_file = self._get_default_config_path()

        # Initialize storage availability flag
        self._storage_available = True

        # Try to ensure the parent directory exists and path is writable
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            # Test write access by attempting to touch the file
            if not self.config_file.exists():
                self.config_file.touch()
                self.config_file.unlink()  # Clean up test file
            logger.info(
                f"Printer storage initialized with config file: {self.config_file}"
            )
        except (PermissionError, OSError) as e:
            self._storage_available = False
            logger.warning(
                f"Failed to create printer storage directory "
                f"{self.config_file.parent}: {e}. "
                "Persistent printer storage will be disabled."
            )
            logger.info(
                f"Printer storage initialized with config file: "
                f"{self.config_file} (unavailable)"
            )

    def _get_default_config_path(self) -> Path:
        """Determine the appropriate default config file path based on environment.

        Returns:
            Path: Appropriate path for the current environment
        """
        # Check if we're running in a Docker container (common indicator: /app exists)
        docker_path = Path("/app/data/printers.json")
        if Path("/app").exists() and os.access("/app", os.W_OK):
            return docker_path

        # For development/local environments, use a local data directory
        # Try current working directory first
        local_data_dir = Path.cwd() / "data"
        try:
            local_data_dir.mkdir(exist_ok=True)
            if os.access(local_data_dir, os.W_OK):
                return local_data_dir / "printers.json"
        except (PermissionError, OSError):
            pass

        # Fall back to user's home directory
        try:
            home_data_dir = Path.home() / ".lanbu-handy"
            home_data_dir.mkdir(exist_ok=True)
            if os.access(home_data_dir, os.W_OK):
                return home_data_dir / "printers.json"
        except (PermissionError, OSError):
            pass

        # Last resort: use temp directory (non-persistent)
        import tempfile

        temp_dir = Path(tempfile.gettempdir()) / "lanbu-handy"
        try:
            temp_dir.mkdir(exist_ok=True)
            return temp_dir / "printers.json"
        except (PermissionError, OSError):
            # If all else fails, use the original docker path
            # (will likely fail but preserves original behavior)
            return docker_path

    def is_storage_available(self) -> bool:
        """Check if persistent storage is available.

        Returns:
            bool: True if storage is available, False otherwise
        """
        return self._storage_available

    def load_printers(self) -> List[PrinterConfig]:
        """Load printer configurations from the persistent storage file.

        Returns:
            List[PrinterConfig]: List of stored printer configurations

        Raises:
            PrinterStorageError: If loading fails
        """
        if not self._storage_available:
            logger.debug("Printer storage unavailable - returning empty list")
            return []

        if not self.config_file.exists():
            logger.info(
                "No persistent printer config file found - returning empty list"
            )
            return []

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict) or "printers" not in data:
                logger.warning("Invalid config file format - returning empty list")
                return []

            printers = []
            for printer_data in data["printers"]:
                try:
                    printer = PrinterConfig(
                        name=printer_data["name"],
                        ip=printer_data["ip"],
                        access_code=printer_data.get("access_code", ""),
                        serial_number=printer_data.get("serial_number", ""),
                    )
                    printers.append(printer)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping invalid printer config: {e}")
                    continue

            logger.info(f"Loaded {len(printers)} printers from persistent storage")
            return printers

        except json.JSONDecodeError as e:
            raise PrinterStorageError(f"Invalid JSON in config file: {e}")
        except IOError as e:
            raise PrinterStorageError(f"Failed to read config file: {e}")
        except Exception as e:
            raise PrinterStorageError(f"Unexpected error loading printers: {e}")

    def save_printers(self, printers: List[PrinterConfig]) -> None:
        """Save printer configurations to the persistent storage file.

        Args:
            printers: List of printer configurations to save

        Raises:
            PrinterStorageError: If saving fails
        """
        if not self._storage_available:
            logger.warning("Printer storage unavailable - cannot save printers")
            raise PrinterStorageError(
                "Persistent storage is not available. Check directory permissions."
            )

        try:
            # Convert printers to serializable format
            printer_data = []
            for printer in printers:
                printer_data.append(
                    {
                        "name": printer.name,
                        "ip": printer.ip,
                        "access_code": printer.access_code,
                        "serial_number": printer.serial_number,
                    }
                )

            # Create the data structure
            data = {"version": "1.0", "printers": printer_data}

            # Ensure the parent directory exists before writing
            try:
                self.config_file.parent.mkdir(parents=True, exist_ok=True)
            except (PermissionError, OSError) as e:
                raise PrinterStorageError(f"Cannot create storage directory: {e}")

            # Write to a temp file first, then rename for atomic operation
            temp_file = self.config_file.with_suffix(".tmp")

            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.rename(self.config_file)

            logger.info(f"Saved {len(printers)} printers to persistent storage")

        except IOError as e:
            raise PrinterStorageError(f"Failed to write config file: {e}")
        except Exception as e:
            raise PrinterStorageError(f"Unexpected error saving printers: {e}")

    def add_printer(self, printer: PrinterConfig) -> None:
        """Add a printer to persistent storage.

        Args:
            printer: Printer configuration to add

        Raises:
            PrinterStorageError: If the printer already exists or saving fails
        """
        if not self._storage_available:
            logger.warning(
                "Printer storage unavailable - cannot add printer persistently"
            )
            raise PrinterStorageError(
                "Persistent storage is not available. Check directory permissions."
            )

        printers = self.load_printers()

        # Check if printer already exists (by IP)
        for existing_printer in printers:
            if existing_printer.ip == printer.ip:
                raise PrinterStorageError(
                    f"Printer with IP {printer.ip} already exists"
                )

        printers.append(printer)
        self.save_printers(printers)

    def remove_printer(self, ip: str) -> bool:
        """Remove a printer from persistent storage by IP address.

        Args:
            ip: IP address of the printer to remove

        Returns:
            bool: True if printer was found and removed, False if not found

        Raises:
            PrinterStorageError: If saving fails
        """
        printers = self.load_printers()
        original_count = len(printers)

        # Remove printers with matching IP
        printers = [p for p in printers if p.ip != ip]

        if len(printers) < original_count:
            self.save_printers(printers)
            logger.info(f"Removed printer with IP {ip} from persistent storage")
            return True
        else:
            logger.info(f"No printer found with IP {ip} to remove")
            return False

    def update_printer(
        self,
        ip: str,
        name: Optional[str] = None,
        access_code: Optional[str] = None,
        serial_number: Optional[str] = None,
    ) -> bool:
        """Update an existing printer configuration.

        Args:
            ip: IP address of the printer to update
            name: New name for the printer (if provided)
            access_code: New access code for the printer (if provided)
            serial_number: New serial number for the printer (if provided)

        Returns:
            bool: True if printer was found and updated, False if not found

        Raises:
            PrinterStorageError: If saving fails
        """
        printers = self.load_printers()
        found = False

        for printer in printers:
            if printer.ip == ip:
                if name is not None:
                    printer.name = name
                if access_code is not None:
                    printer.access_code = access_code
                if serial_number is not None:
                    printer.serial_number = serial_number
                found = True
                break

        if found:
            self.save_printers(printers)
            logger.info(f"Updated printer with IP {ip} in persistent storage")
            return True
        else:
            logger.info(f"No printer found with IP {ip} to update")
            return False

    def get_printer_by_ip(self, ip: str) -> Optional[PrinterConfig]:
        """Get a specific printer configuration by IP address.

        Args:
            ip: IP address of the printer to find

        Returns:
            PrinterConfig: The printer configuration if found, None otherwise
        """
        printers = self.load_printers()

        for printer in printers:
            if printer.ip == ip:
                return printer

        return None

    def clear_all_printers(self) -> None:
        """Remove all printers from persistent storage.

        Raises:
            PrinterStorageError: If saving fails
        """
        self.save_printers([])
        logger.info("Cleared all printers from persistent storage")


# Global printer storage instance - initialized lazily
_printer_storage = None


def get_printer_storage() -> PrinterStorage:
    """Get the global printer storage instance, creating it if necessary."""
    global _printer_storage
    if _printer_storage is None:
        _printer_storage = PrinterStorage()
    return _printer_storage


def reset_printer_storage():
    """Reset the global printer storage instance. For testing purposes only."""
    global _printer_storage
    _printer_storage = None
