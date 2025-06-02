"""
Printer communication service for LANbu Handy.

Handles FTP communication with Bambu Lab printers in LAN-only mode,
including G-code file uploads and basic error handling.
"""

import ftplib
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from app.config import PrinterConfig

logger = logging.getLogger(__name__)


class PrinterCommunicationError(Exception):
    """Base exception for printer communication errors."""
    pass


class PrinterConnectionError(PrinterCommunicationError):
    """Exception raised when unable to connect to printer FTP server."""
    pass


class PrinterAuthenticationError(PrinterCommunicationError):
    """Exception raised when FTP authentication fails."""
    pass


class PrinterFileTransferError(PrinterCommunicationError):
    """Exception raised when file transfer fails."""
    pass


@dataclass
class FTPUploadResult:
    """Result of an FTP upload operation."""
    success: bool
    message: str
    remote_path: str = None
    error_details: str = None


class PrinterService:
    """Service for communicating with Bambu Lab printers via FTP."""
    
    # Default FTP settings for Bambu Lab printers
    DEFAULT_FTP_PORT = 21
    DEFAULT_FTP_TIMEOUT = 30
    DEFAULT_UPLOAD_PATH = "/upload"  # Common path for Bambu printers
    
    def __init__(self, timeout: int = DEFAULT_FTP_TIMEOUT):
        """Initialize the printer service.
        
        Args:
            timeout: FTP connection timeout in seconds
        """
        self.timeout = timeout
    
    def upload_gcode(
        self,
        printer_config: PrinterConfig,
        gcode_file_path: Path,
        remote_filename: Optional[str] = None,
        remote_path: str = DEFAULT_UPLOAD_PATH
    ) -> FTPUploadResult:
        """Upload a G-code file to the printer via FTP.
        
        Args:
            printer_config: Configuration for the target printer
            gcode_file_path: Local path to the G-code file
            remote_filename: Filename to use on the printer (defaults to local filename)
            remote_path: Remote directory path on the printer
            
        Returns:
            FTPUploadResult: Result of the upload operation
            
        Raises:
            PrinterCommunicationError: If upload fails with details
        """
        if not gcode_file_path.exists():
            raise PrinterFileTransferError(
                f"G-code file not found: {gcode_file_path}"
            )
        
        if not gcode_file_path.is_file():
            raise PrinterFileTransferError(
                f"Path is not a file: {gcode_file_path}"
            )
        
        # Use original filename if no remote filename specified
        if remote_filename is None:
            remote_filename = gcode_file_path.name
        
        # Construct full remote path
        full_remote_path = f"{remote_path.rstrip('/')}/{remote_filename}"
        
        logger.info(f"Uploading G-code to printer {printer_config.name} "
                   f"({printer_config.ip}): {gcode_file_path.name}")
        
        ftp = None
        try:
            # Connect to the printer's FTP server
            ftp = ftplib.FTP()
            ftp.connect(printer_config.ip, self.DEFAULT_FTP_PORT, self.timeout)
            
            # Authenticate - Bambu printers typically use anonymous login
            # or specific credentials based on access code
            try:
                # Try anonymous login first (common for LAN mode)
                ftp.login()
                logger.debug(f"Connected to printer {printer_config.ip} "
                           f"using anonymous FTP")
            except ftplib.error_perm:
                # If anonymous fails, try with access code as password
                try:
                    ftp.login("user", printer_config.access_code)
                    logger.debug(f"Connected to printer {printer_config.ip} "
                               f"using access code authentication")
                except ftplib.error_perm as e:
                    raise PrinterAuthenticationError(
                        f"FTP authentication failed for printer "
                        f"{printer_config.name}: {str(e)}"
                    )
            
            # Change to the target directory (create if needed)
            try:
                ftp.cwd(remote_path)
            except ftplib.error_perm:
                # Directory might not exist, try to create it
                try:
                    ftp.mkd(remote_path)
                    ftp.cwd(remote_path)
                    logger.debug(f"Created remote directory: {remote_path}")
                except ftplib.error_perm as e:
                    logger.warning(f"Could not create/access directory "
                                 f"{remote_path}: {e}")
                    # Continue anyway, upload to current directory
            
            # Upload the file in binary mode
            with open(gcode_file_path, 'rb') as file:
                upload_command = f"STOR {remote_filename}"
                ftp.storbinary(upload_command, file)
            
            # Verify the upload by checking file size
            try:
                remote_size = ftp.size(remote_filename)
                local_size = gcode_file_path.stat().st_size
                
                if remote_size == local_size:
                    logger.info(f"Successfully uploaded {gcode_file_path.name} "
                              f"to printer {printer_config.name} "
                              f"({local_size} bytes)")
                else:
                    logger.warning(f"File size mismatch after upload: "
                                 f"local={local_size}, remote={remote_size}")
            except (ftplib.error_perm, OSError):
                # Size verification failed, but upload might still be successful
                logger.debug("Could not verify upload file size")
            
            return FTPUploadResult(
                success=True,
                message=f"G-code uploaded successfully to {printer_config.name}",
                remote_path=full_remote_path
            )
            
        except PrinterAuthenticationError:
            # Re-raise our custom authentication errors
            raise
            
        except PrinterFileTransferError:
            # Re-raise our custom file transfer errors
            raise
            
        except PrinterConnectionError:
            # Re-raise our custom connection errors
            raise
            
        except ftplib.error_perm as e:
            error_msg = f"FTP permission error: {str(e)}"
            logger.error(f"Upload failed to {printer_config.name}: {error_msg}")
            raise PrinterAuthenticationError(error_msg)
            
        except ftplib.error_temp as e:
            error_msg = f"FTP temporary error: {str(e)}"
            logger.error(f"Upload failed to {printer_config.name}: {error_msg}")
            raise PrinterFileTransferError(error_msg)
            
        except (ftplib.error_proto, ConnectionError, OSError) as e:
            error_msg = f"FTP connection error: {str(e)}"
            logger.error(f"Upload failed to {printer_config.name}: {error_msg}")
            raise PrinterConnectionError(error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error during FTP upload: {str(e)}"
            logger.error(f"Upload failed to {printer_config.name}: {error_msg}")
            raise PrinterCommunicationError(error_msg)
            
        finally:
            # Always close the FTP connection
            if ftp:
                try:
                    ftp.quit()
                    logger.debug(f"Closed FTP connection to {printer_config.ip}")
                except Exception:
                    # If quit fails, try close
                    try:
                        ftp.close()
                    except Exception:
                        pass  # Ignore errors during cleanup
    
    def test_connection(self, printer_config: PrinterConfig) -> bool:
        """Test FTP connection to a printer without uploading.
        
        Args:
            printer_config: Configuration for the target printer
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        ftp = None
        try:
            logger.info(f"Testing FTP connection to printer {printer_config.name} "
                       f"({printer_config.ip})")
            
            ftp = ftplib.FTP()
            ftp.connect(printer_config.ip, self.DEFAULT_FTP_PORT, self.timeout)
            
            # Try authentication
            try:
                ftp.login()
                logger.debug("Anonymous FTP login successful")
            except ftplib.error_perm:
                ftp.login("user", printer_config.access_code)
                logger.debug("Access code authentication successful")
            
            logger.info(f"FTP connection test successful for {printer_config.name}")
            return True
            
        except Exception as e:
            logger.warning(f"FTP connection test failed for {printer_config.name}: {e}")
            return False
            
        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:
                    try:
                        ftp.close()
                    except Exception:
                        pass