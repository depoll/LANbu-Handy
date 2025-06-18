"""
Printer configuration data class.

Separated from config.py to avoid circular imports.
"""

import re
from dataclasses import dataclass, field


def generate_canonical_id(name: str) -> str:
    """Generate a URL-safe canonical ID from a printer name.

    Converts special characters to underscores and ensures the ID is
    suitable for use in URLs and as identifiers.

    Args:
        name: The display name of the printer

    Returns:
        A canonical ID safe for URLs
    """
    # Replace non-alphanumeric characters with underscores
    canonical = re.sub(r"[^a-zA-Z0-9]+", "_", name)
    # Remove leading/trailing underscores
    canonical = canonical.strip("_")
    # Convert to lowercase for consistency
    canonical = canonical.lower()
    # If empty, use a default
    if not canonical:
        canonical = "printer"
    return canonical


@dataclass
class PrinterConfig:
    """Configuration for a single Bambu printer."""

    name: str
    ip: str
    access_code: str
    serial_number: str = ""
    canonical_id: str = field(default="", init=False)

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
        self.serial_number = self.serial_number.strip() if self.serial_number else ""

        # Generate canonical ID if not set
        if not self.canonical_id:
            self.canonical_id = generate_canonical_id(self.name)
