"""
FTP wrapper using curl for X1C printer support.

Since Python's ftplib doesn't support SSL session reuse properly,
we use curl as a subprocess which has full support for FTPS with session reuse.
"""

import logging
import shutil
import subprocess
import urllib.parse
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
        # URL-encode the remote path to handle special characters and spaces
        encoded_path = urllib.parse.quote(remote_path, safe="/") if remote_path else ""
        url = f"ftps://{self.host}:{self.port}/{encoded_path}"

        if operation == "upload" and local_file:
            cmd.extend(["-T", local_file])  # Upload file
        elif operation == "list":
            cmd.extend(["-l"])  # List directory
        elif operation == "download":
            cmd.extend(["-o", local_file] if local_file else ["-O"])  # Download
        elif operation == "delete":
            # For DELE command, we don't URL-encode as it's an FTP command, not a URL
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

    def create_directory(self, remote_dir: str) -> Tuple[bool, str]:
        """
        Create a directory on the FTP server.

        Args:
            remote_dir: Remote directory to create

        Returns:
            Tuple of (success, message)
        """
        try:
            # Use curl with MKD command to create directory
            cmd = [
                "curl",
                "--ftp-ssl",
                "--ftp-ssl-reqd",
                "--ftp-pasv",
                "--ssl-reqd",
                "--insecure",
                "--connect-timeout",
                str(self.timeout),
                "--user",
                f"{self.username}:{self.password}",
                "-Q",
                f"MKD {remote_dir}",
                f"ftps://{self.host}:{self.port}/",
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout
            )

            if result.returncode == 0 or "already exists" in result.stderr.lower():
                return True, f"Directory {remote_dir} created or already exists"
            else:
                return False, f"Failed to create directory: {result.stderr}"

        except Exception as e:
            return False, f"Error creating directory: {str(e)}"

    def upload_file(
        self,
        local_path: Path,
        remote_filename: Optional[str] = None,
        remote_dir: str = "",
        progress_callback: Optional[callable] = None,
    ) -> Tuple[bool, str]:
        """
        Upload a file to the FTP server with progress reporting.

        Args:
            local_path: Local file to upload
            remote_filename: Remote filename (defaults to local filename)
            remote_dir: Remote directory (defaults to root)
            progress_callback: Optional callback for progress updates (percent, message)

        Returns:
            Tuple of (success, message)
        """
        if not local_path.exists():
            return False, f"Local file not found: {local_path}"

        if remote_filename is None:
            remote_filename = local_path.name

        # Create directory if specified
        if remote_dir:
            dir_created, dir_msg = self.create_directory(remote_dir)
            if not dir_created and "already exists" not in dir_msg.lower():
                logger.warning(f"Failed to create directory {remote_dir}: {dir_msg}")
                # Continue anyway - directory might exist

        # Build remote path
        if remote_dir:
            remote_path = f"{remote_dir.rstrip('/')}/{remote_filename}"
        else:
            remote_path = remote_filename

        # Get file size for progress reporting
        file_size = local_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)

        try:
            # Add progress bar to curl command
            cmd = self._build_curl_cmd("upload", remote_path, str(local_path))

            # Add progress meter option to get percentage output
            # Remove --progress-bar as it doesn't give us parseable output
            cmd.insert(1, "-#")  # This gives us the progress meter with percentage

            logger.info(
                (
                    f"Uploading {local_path.name} ({file_size_mb:.1f} MB) to "
                    f"{self.host}:{remote_path}"
                )
            )

            # Report initial progress
            if progress_callback:
                progress_callback(
                    0, f"Starting upload of {local_path.name} ({file_size_mb:.1f} MB)"
                )

            # Run curl command with real-time output parsing
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # Parse curl's progress output
            last_percent = 0
            stderr_lines = []

            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    stderr_lines.append(line.strip())
                    # Parse curl progress meter output
                    # Format: "############ 100.0%"
                    # or: "#####                7.1%"
                    if "%" in line and "#" in line:
                        try:
                            # Extract percentage from end of line
                            percent_str = line.strip().split()[-1]
                            if percent_str.endswith("%"):
                                percent = int(float(percent_str[:-1]))
                                if percent != last_percent and progress_callback:
                                    progress_callback(
                                        percent, f"Uploading... {percent}%"
                                    )
                                    last_percent = percent
                        except (ValueError, IndexError):
                            pass
                    # Also check for the summary line format
                    elif "%" in line and ("Average" in line or "Total" in line):
                        # Parse lines like: "  % Total    % Received % Xferd"
                        # Next line would have the actual percentages
                        pass

            # Get the return code
            return_code = process.wait()
            stderr_output = "".join(stderr_lines)

            if return_code == 0:
                logger.info(f"Successfully uploaded {local_path.name} to {remote_path}")
                if progress_callback:
                    progress_callback(100, f"Upload complete: {remote_path}")
                return True, f"File uploaded successfully to {remote_path}"
            else:
                error_msg = stderr_output
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
    progress_callback: Optional[callable] = None,
) -> Tuple[bool, str]:
    """
    Helper function to upload G-code to X1C printer using curl.

    Args:
        printer_ip: Printer IP address
        access_code: Printer access code
        gcode_path: Path to G-code file
        remote_filename: Remote filename (optional)
        progress_callback: Optional callback for progress updates (percent, message)

    Returns:
        Tuple of (success, message)
    """
    client = CurlFTPSClient(host=printer_ip, password=access_code, timeout=30)

    # Test connection first
    if not client.test_connection():
        return False, "Failed to connect to printer"

    # Upload the file with progress callback
    return client.upload_file(
        gcode_path, remote_filename, progress_callback=progress_callback
    )
