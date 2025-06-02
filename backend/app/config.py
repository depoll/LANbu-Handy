"""
Configuration management for LANbu Handy.

Handles reading environment variables and application configuration.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Config:
    """Application configuration class."""
    
    def __init__(self):
        """Initialize configuration by reading environment variables."""
        self.bambu_printer_ip: Optional[str] = self._load_printer_ip()
    
    def _load_printer_ip(self) -> Optional[str]:
        """Load Bambu printer IP from environment variable.
        
        Returns:
            str: The printer IP address if set, None otherwise
        """
        printer_ip = os.getenv("BAMBU_PRINTER_IP")
        
        if printer_ip:
            printer_ip = printer_ip.strip()
            if printer_ip:
                logger.info(f"Bambu printer IP configured: {printer_ip}")
                return printer_ip
        
        logger.warning("BAMBU_PRINTER_IP environment variable not set. "
                      "Printer communication will not be available.")
        return None
    
    def is_printer_configured(self) -> bool:
        """Check if printer IP is configured.
        
        Returns:
            bool: True if printer IP is available, False otherwise
        """
        return self.bambu_printer_ip is not None
    
    def get_printer_ip(self) -> Optional[str]:
        """Get the configured printer IP address.
        
        Returns:
            str: The printer IP address if configured, None otherwise
        """
        return self.bambu_printer_ip


# Global configuration instance
config = Config()