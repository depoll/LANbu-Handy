"""
FTP wrapper using curl for X1C printer support.

Since Python's ftplib doesn't support SSL session reuse properly,
we use curl as a subprocess which has full support for FTPS with session reuse.
"""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class CurlFTPSClient:
    """FTPS client using curl for X1C compatibility."""

    def __init__(
        self,
        host: str,
        port: int = 990,
        username: str = "bblp",
        password: str = "",
        timeout: int = 30,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout

        # Check if curl is available
        if not shutil.which("curl"):
            raise RuntimeError("curl command not found. Please install curl.")

    def _build_curl_cmd(
        self, operation: str, remote_path: str = "", local_file: Optional[str] = None
    ) -> list:
        """Build curl command for FTPS operations."""
        # Base curl command with implicit FTPS
        cmd = [
            "curl",
            "--ftp-ssl",  # Use FTPS
            "--ftp-ssl-reqd",  # Require SSL
            "--ftp-pasv",  # Use passive mode
            "--ssl-reqd",  # Require SSL for data connections
            "--insecure",  # Don't verify certificates (like FileZilla)
            "--connect-timeout",
            str(self.timeout),
            "--user",
            f"{self.username}:{self.password}",
        ]

        # Build URL - for implicit FTPS, use ftps:// protocol
        url = f"ftps://{self.host}:{self.port}/{remote_path}"

        if operation == "upload" and local_file:
            cmd.extend(["-T", local_file])  # Upload file
        elif operation == "list":
            cmd.extend(["-l"])  # List directory
        elif operation == "download":
            cmd.extend(["-o", local_file] if local_file else ["-O"])  # Download
        elif operation == "delete":
            cmd.extend(["-Q", f"DELE {remote_path}"])  # Delete file
            url = f"ftps://{self.host}:{self.port}/"  # Use root for QUOTE commands

        cmd.append(url)
        return cmd

    def test_connection(self) -> bool:
        """Test if we can connect to the FTP server."""
        try:
            cmd = self._build_curl_cmd("list", "")
            logger.debug(
                f"Testing connection with command: {' '.join(cmd[:-2] + ['***'])}"
            )

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout
            )

            if result.returncode == 0:
                logger.info("FTP connection test successful")
                return True
            else:
                logger.error(f"FTP connection test failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"FTP connection test error: {e}")
            return False

    def upload_file(
        self,
        local_path: Path,
        remote_filename: Optional[str] = None,
        remote_dir: str = "",
    ) -> Tuple[bool, str]:
        """
        Upload a file to the FTP server.

        Args:
            local_path: Local file to upload
            remote_filename: Remote filename (defaults to local filename)
            remote_dir: Remote directory (defaults to root)

        Returns:
            Tuple of (success, message)
        """
        if not local_path.exists():
            return False, f"Local file not found: {local_path}"

        if remote_filename is None:
            remote_filename = local_path.name

        # Build remote path
        if remote_dir:
            remote_path = f"{remote_dir.rstrip('/')}/{remote_filename}"
        else:
            remote_path = remote_filename

        try:
            cmd = self._build_curl_cmd("upload", remote_path, str(local_path))
            logger.info(f"Uploading {local_path.name} to {self.host}:{remote_path}")

            # Run curl command
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout + 30
            )

            if result.returncode == 0:
                logger.info(f"Successfully uploaded {local_path.name}")
                return True, f"File uploaded successfully to {remote_path}"
            else:
                error_msg = result.stderr or result.stdout
                logger.error(f"Upload failed: {error_msg}")
                return False, f"Upload failed: {error_msg}"

        except subprocess.TimeoutExpired:
            return False, "Upload timed out"
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return False, f"Upload error: {str(e)}"

    def list_files(self, remote_dir: str = "") -> Tuple[bool, list]:
        """
        List files in a directory.

        Returns:
            Tuple of (success, list of filenames)
        """
        try:
            cmd = self._build_curl_cmd("list", remote_dir)
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout
            )

            if result.returncode == 0:
                # Parse the listing - curl -l returns just filenames
                files = [
                    f.strip() for f in result.stdout.strip().split("\n") if f.strip()
                ]
                return True, files
            else:
                logger.error(f"List failed: {result.stderr}")
                return False, []

        except Exception as e:
            logger.error(f"List error: {e}")
            return False, []


def upload_gcode_to_x1c(
    printer_ip: str,
    access_code: str,
    gcode_path: Path,
    remote_filename: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Helper function to upload G-code to X1C printer using curl.

    Args:
        printer_ip: Printer IP address
        access_code: Printer access code
        gcode_path: Path to G-code file
        remote_filename: Remote filename (optional)

    Returns:
        Tuple of (success, message)
    """
    client = CurlFTPSClient(host=printer_ip, password=access_code, timeout=30)

    # Test connection first
    if not client.test_connection():
        return False, "Failed to connect to printer"

    # Upload the file
    return client.upload_file(gcode_path, remote_filename)
