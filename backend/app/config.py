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
        if not self.access_code or not self.access_code.strip():
            raise ValueError("Printer access code cannot be empty")

        # Strip whitespace
        self.name = self.name.strip()
        self.ip = self.ip.strip()
        self.access_code = self.access_code.strip()


class Config:
    """Application configuration class."""

    def __init__(self):
        """Initialize configuration by reading environment variables."""
        self.printers: List[PrinterConfig] = self._load_printers()

    def _load_printers(self) -> List[PrinterConfig]:
        """Load Bambu printer configurations from environment variables.

        Supports two formats:
        1. New format: BAMBU_PRINTERS JSON array
        2. Legacy format: BAMBU_PRINTER_IP (for backward compatibility)

        Returns:
            List[PrinterConfig]: List of configured printers
        """
        printers = []

        # Try new format first: BAMBU_PRINTERS JSON
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

        # Fall back to legacy format: BAMBU_PRINTER_IP
        legacy_ip = os.getenv("BAMBU_PRINTER_IP")
        if legacy_ip:
            legacy_ip = legacy_ip.strip()
            if legacy_ip:
                # For legacy format, we need an access code too
                legacy_access_code = os.getenv("BAMBU_PRINTER_ACCESS_CODE", "")
                if not legacy_access_code.strip():
                    logger.warning(
                        "BAMBU_PRINTER_IP is set but "
                        "BAMBU_PRINTER_ACCESS_CODE is missing. "
                        "Please provide access code or use "
                        "BAMBU_PRINTERS format."
                    )
                    return []

                try:
                    printer = PrinterConfig(
                        name="Default Printer",
                        ip=legacy_ip,
                        access_code=legacy_access_code.strip(),
                    )
                    printers.append(printer)
                    logger.info(
                        f"Configured legacy printer: {printer.name} " f"at {printer.ip}"
                    )
                    return printers
                except ValueError as e:
                    logger.error(f"Invalid legacy printer configuration: {e}")

        # No printers configured
        logger.warning(
            "No printer configuration found. Set BAMBU_PRINTERS "
            "(JSON format) or BAMBU_PRINTER_IP + "
            "BAMBU_PRINTER_ACCESS_CODE for legacy format. "
            "Printer communication will not be available."
        )
        return []

    def is_printer_configured(self) -> bool:
        """Check if any printers are configured.

        Returns:
            bool: True if at least one printer is configured, False otherwise
        """
        return len(self.printers) > 0

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

        Returns:
            PrinterConfig: The first printer configuration if any exists,
                         None otherwise
        """
        return self.printers[0] if self.printers else None

    # Legacy methods for backward compatibility
    def get_printer_ip(self) -> Optional[str]:
        """Get the first printer's IP address (legacy compatibility).

        Returns:
            str: The first printer's IP address if configured,
                None otherwise
        """
        default_printer = self.get_default_printer()
        return default_printer.ip if default_printer else None


# Global configuration instance
config = Config()
