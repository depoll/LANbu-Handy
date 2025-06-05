"""
Configuration management for LANbu Handy.

Handles reading environment variables and application configuration.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PrinterConfig:
    """Configuration for a single Bambu printer."""

    name: str
    ip: str
    access_code: str

    def __post_init__(self):
        """Validate printer configuration after initialization."""
        if not self.name or not self.name.strip():
            raise ValueError("Printer name cannot be empty")
        if not self.ip or not self.ip.strip():
            raise ValueError("Printer IP cannot be empty")
        # Access code can be empty for LAN-only mode
        # if not self.access_code or not self.access_code.strip():
        #     raise ValueError("Printer access code cannot be empty")

        # Strip whitespace
        self.name = self.name.strip()
        self.ip = self.ip.strip()
        self.access_code = self.access_code.strip() if self.access_code else ""


class Config:
    """Application configuration class."""

    def __init__(self):
        """Initialize configuration by reading environment variables and
        persistent storage."""
        self.printers: List[PrinterConfig] = self._load_printers()
        self.runtime_active_printer: Optional[PrinterConfig] = None

    def _load_printers(self) -> List[PrinterConfig]:
        """Load Bambu printer configurations from all sources.

        Loads printers from:
        1. Persistent storage file (if available)
        2. Environment variables (for backward compatibility)

        Returns:
            List[PrinterConfig]: Combined list of configured printers
        """
        all_printers = []

        # First, try to load from persistent storage
        try:
            from app.printer_storage import get_printer_storage

            printer_storage = get_printer_storage()
            persistent_printers = printer_storage.load_printers()
            all_printers.extend(persistent_printers)
            if persistent_printers:
                logger.info(
                    f"Loaded {len(persistent_printers)} printers "
                    f"from persistent storage"
                )
        except Exception as e:
            logger.warning(f"Failed to load printers from persistent storage: {e}")

        # Then load from environment variables (for backward compatibility)
        env_printers = self._load_printers_from_env()

        # Add environment printers that don't conflict with persistent ones
        # (same IP address = conflict)
        persistent_ips = {p.ip for p in all_printers}
        for env_printer in env_printers:
            if env_printer.ip not in persistent_ips:
                all_printers.append(env_printer)
                logger.info(
                    f"Added environment printer: {env_printer.name} "
                    f"at {env_printer.ip}"
                )
            else:
                logger.info(
                    f"Skipping environment printer "
                    f"{env_printer.name} - IP {env_printer.ip} "
                    f"already exists in persistent storage"
                )

        if not all_printers:
            logger.warning(
                "No printer configuration found. Set BAMBU_PRINTERS "
                "(JSON format) or add printers via the UI. "
                "Printer communication will not be available."
            )

        return all_printers

    def _load_printers_from_env(self) -> List[PrinterConfig]:
        """Load Bambu printer configurations from environment variables.

        Supports BAMBU_PRINTERS JSON array format.

        Returns:
            List[PrinterConfig]: List of configured printers from environment
        """
        printers = []

        # Load from BAMBU_PRINTERS JSON
        bambu_printers_json = os.getenv("BAMBU_PRINTERS")
        if bambu_printers_json:
            try:
                bambu_printers_json = bambu_printers_json.strip()
                if bambu_printers_json:
                    printers_data = json.loads(bambu_printers_json)
                    if not isinstance(printers_data, list):
                        logger.error("BAMBU_PRINTERS must be a JSON array")
                        return []

                    for i, printer_data in enumerate(printers_data):
                        try:
                            if not isinstance(printer_data, dict):
                                logger.error(f"Printer {i} must be a " f"JSON object")
                                continue

                            name = printer_data.get("name", f"Printer {i+1}")
                            ip = printer_data.get("ip", "")
                            access_code = printer_data.get("access_code", "")

                            printer = PrinterConfig(
                                name=name, ip=ip, access_code=access_code
                            )
                            printers.append(printer)
                            logger.info(
                                f"Configured printer: {printer.name} "
                                f"at {printer.ip}"
                            )

                        except (ValueError, KeyError) as e:
                            logger.error(
                                f"Invalid configuration for " f"printer {i}: {e}"
                            )
                            continue

                    if printers:
                        return printers
                    else:
                        logger.warning("No valid printers found in " "BAMBU_PRINTERS")

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in BAMBU_PRINTERS: {e}")

        # No printers configured via environment variables
        return []

    def is_printer_configured(self) -> bool:
        """Check if any printers are configured.

        Returns:
            bool: True if at least one printer is configured or if an active
                 printer is set, False otherwise
        """
        return len(self.printers) > 0 or self.runtime_active_printer is not None

    def get_printers(self) -> List[PrinterConfig]:
        """Get all configured printers.

        Returns:
            List[PrinterConfig]: List of configured printers
        """
        return self.printers.copy()

    def get_printer_by_name(self, name: str) -> Optional[PrinterConfig]:
        """Get a printer configuration by name.

        Args:
            name: The printer name to search for

        Returns:
            PrinterConfig: The printer configuration if found, None otherwise
        """
        for printer in self.printers:
            if printer.name == name:
                return printer
        return None

    def get_default_printer(self) -> Optional[PrinterConfig]:
        """Get the default (first) printer configuration.

        Returns the runtime active printer if set, otherwise the first
        configured printer.

        Returns:
            PrinterConfig: The active printer configuration if any exists,
                         None otherwise
        """
        if self.runtime_active_printer:
            return self.runtime_active_printer
        return self.printers[0] if self.printers else None

    def set_active_printer(
        self, ip: str, access_code: str = "", name: str = None
    ) -> PrinterConfig:
        """Set the active printer for the current session.

        Args:
            ip: Printer IP address
            access_code: Optional printer access code
            name: Optional printer name (defaults to "Active Printer")

        Returns:
            PrinterConfig: The newly set active printer configuration

        Raises:
            ValueError: If the IP address is invalid
        """
        if not ip or not ip.strip():
            raise ValueError("Printer IP cannot be empty")

        if name is None:
            name = "Active Printer"

        printer_config = PrinterConfig(
            name=name, ip=ip.strip(), access_code=access_code.strip()
        )

        self.runtime_active_printer = printer_config
        logger.info(f"Set active printer: {printer_config.name} at {printer_config.ip}")
        return printer_config

    def get_active_printer(self) -> Optional[PrinterConfig]:
        """Get the currently active printer.

        Returns:
            PrinterConfig: The active printer if set, None otherwise
        """
        return self.runtime_active_printer

    def clear_active_printer(self) -> None:
        """Clear the currently active printer."""
        if self.runtime_active_printer:
            logger.info(f"Cleared active printer: {self.runtime_active_printer.name}")
            self.runtime_active_printer = None

    def add_persistent_printer(self, printer: PrinterConfig) -> None:
        """Add a printer to persistent storage and update the current list.

        Args:
            printer: Printer configuration to add

        Raises:
            ValueError: If printer already exists or storage fails
        """
        try:
            from app.printer_storage import get_printer_storage

            printer_storage = get_printer_storage()
            printer_storage.add_printer(printer)

            # Reload printers to include the new one
            self.printers = self._load_printers()
            logger.info(f"Added persistent printer: {printer.name} at {printer.ip}")

        except Exception as e:
            logger.error(f"Failed to add persistent printer: {e}")
            raise ValueError(f"Failed to add printer: {e}")

    def remove_persistent_printer(self, ip: str) -> bool:
        """Remove a printer from persistent storage and update the current list.

        Args:
            ip: IP address of the printer to remove

        Returns:
            bool: True if printer was removed, False if not found
        """
        try:
            from app.printer_storage import get_printer_storage

            printer_storage = get_printer_storage()
            removed = printer_storage.remove_printer(ip)

            if removed:
                # Reload printers to reflect the removal
                self.printers = self._load_printers()

                # Clear active printer if it was the removed one
                if self.runtime_active_printer and self.runtime_active_printer.ip == ip:
                    self.runtime_active_printer = None
                    logger.info("Cleared active printer as it was removed")

                logger.info(f"Removed persistent printer with IP: {ip}")

            return removed

        except Exception as e:
            logger.error(f"Failed to remove persistent printer: {e}")
            return False

    def update_persistent_printer(
        self, ip: str, name: Optional[str] = None, access_code: Optional[str] = None
    ) -> bool:
        """Update a persistent printer configuration.

        Args:
            ip: IP address of the printer to update
            name: New name for the printer (if provided)
            access_code: New access code for the printer (if provided)

        Returns:
            bool: True if printer was updated, False if not found
        """
        try:
            from app.printer_storage import get_printer_storage

            printer_storage = get_printer_storage()
            updated = printer_storage.update_printer(ip, name, access_code)

            if updated:
                # Reload printers to reflect the changes
                self.printers = self._load_printers()

                # Update active printer if it was the modified one
                if self.runtime_active_printer and self.runtime_active_printer.ip == ip:
                    updated_printer = self.get_printer_by_ip(ip)
                    if updated_printer:
                        self.runtime_active_printer = updated_printer
                        logger.info("Updated active printer configuration")

                logger.info(f"Updated persistent printer with IP: {ip}")

            return updated

        except Exception as e:
            logger.error(f"Failed to update persistent printer: {e}")
            return False

    def get_persistent_printers(self) -> List[PrinterConfig]:
        """Get only the printers stored in persistent storage.

        Returns:
            List[PrinterConfig]: List of persistent printers
                (excludes environment-based ones)
        """
        try:
            from app.printer_storage import get_printer_storage

            printer_storage = get_printer_storage()
            return printer_storage.load_printers()
        except Exception as e:
            logger.error(f"Failed to load persistent printers: {e}")
            return []

    def get_printer_by_ip(self, ip: str) -> Optional[PrinterConfig]:
        """Get a printer configuration by IP address.

        Args:
            ip: The printer IP address to search for

        Returns:
            PrinterConfig: The printer configuration if found, None otherwise
        """
        for printer in self.printers:
            if printer.ip == ip:
                return printer
        return None

    # Legacy methods for backward compatibility
    def get_printer_ip(self) -> Optional[str]:
        """Get the first printer's IP address (legacy compatibility).

        Returns:
            str: The first printer's IP address if configured,
                None otherwise
        """
        default_printer = self.get_default_printer()
        return default_printer.ip if default_printer else None


# Global configuration instance - initialized lazily
_config = None


def get_config() -> Config:
    """Get the global configuration instance, creating it if necessary."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config():
    """Reset the global configuration instance. For testing purposes only."""
    global _config
    _config = None


# For backward compatibility, provide the config instance when accessed
# Use get_config() for new code
config = None
