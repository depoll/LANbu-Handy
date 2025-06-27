"""
FTP client with SSL session reuse support for X1C printers.

This module provides an FTP client that supports implicit FTPS with SSL session
reuse, which is required by Bambu Lab X1C printers.
"""

import ftplib
import logging
import socket
import ssl
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class ImplicitFTP_TLS(ftplib.FTP_TLS):
    """FTP_TLS subclass that supports implicit FTPS with SSL session reuse."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sock = None
        self._session = None  # Store SSL session for reuse

    @property
    def sock(self):
        """Return the socket."""
        return self._sock

    @sock.setter
    def sock(self, value):
        """Set the socket and wrap with SSL if not already wrapped."""
        if value is not None and not isinstance(value, ssl.SSLSocket):
            if not hasattr(self, "ssl_context") or self.ssl_context is None:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                # Enable session caching
                ctx.options |= ssl.OP_NO_TICKET
                self.ssl_context = ctx
            value = self.ssl_context.wrap_socket(value, server_hostname=self.host)
            # Store the session after successful handshake
            self._session = value.session
        self._sock = value

    def ntransfercmd(self, cmd, rest=None) -> Tuple[socket.socket, Optional[int]]:
        """Initialize a data transfer with SSL session reuse."""
        host, port = self.makepasv()
        conn = socket.socket(self.af, socket.SOCK_STREAM)
        conn.settimeout(self.timeout)
        try:
            conn.connect((host, port))
            # Wrap with SSL using the same session
            if self._session and hasattr(self.ssl_context, "wrap_socket"):
                # Create a new SSL context with session reuse
                conn = self.ssl_context.wrap_socket(
                    conn,
                    server_hostname=self.host,
                    session=self._session,  # Reuse the control connection's SSL session
                )
            else:
                # Fallback to regular SSL wrap
                conn = self.ssl_context.wrap_socket(conn, server_hostname=self.host)
        except Exception:
            conn.close()
            raise

        # Send the command
        resp = self.sendcmd(cmd)
        if resp[0] == "2":
            # 2xx response means success
            return conn, self.parse150(resp)
        else:
            conn.close()
            raise ftplib.error_reply(resp)

    def parse150(self, resp):
        """Parse the '150' response for a RETR/STOR command."""
        # Extract size if mentioned in response
        import re

        m = re.match(r"150 .* \((\d+) bytes\)", resp)
        if m:
            return int(m.group(1))
        return None


def connect_implicit_ftps(
    host: str,
    port: int = 990,
    user: str = "bblp",
    password: str = "",
    timeout: int = 30,
    debug: bool = False,
) -> ImplicitFTP_TLS:
    """
    Connect to an implicit FTPS server with SSL session reuse support.

    Args:
        host: FTP server hostname or IP
        port: FTP server port (default 990 for implicit FTPS)
        user: Username for authentication
        password: Password for authentication
        timeout: Connection timeout in seconds
        debug: Enable FTP debugging output

    Returns:
        Connected ImplicitFTP_TLS instance
    """
    ftp = ImplicitFTP_TLS()
    if debug:
        ftp.debugging = 2

    # Set up SSL context
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    # Enable session caching
    ctx.options |= ssl.OP_NO_TICKET
    ftp.ssl_context = ctx

    logger.info(f"Connecting to {host}:{port} using implicit FTPS")
    ftp.connect(host, port, timeout)

    logger.info(f"Logging in as user '{user}'")
    ftp.login(user, password)

    # Enable data protection
    logger.debug("Enabling data connection protection")
    ftp.prot_p()

    # Set passive mode
    logger.debug("Setting passive mode")
    ftp.set_pasv(True)

    return ftp


def test_connection(host: str, user: str = "bblp", password: str = "") -> bool:
    """
    Test if we can connect to an FTP server with SSL session reuse.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        ftp = connect_implicit_ftps(host, user=user, password=password, debug=True)
        # Test with PWD command
        pwd = ftp.pwd()
        logger.info(f"Connected successfully, current directory: {pwd}")

        # Try to list directory
        files = []
        ftp.retrlines("LIST", files.append)
        logger.info(f"Directory listing successful, found {len(files)} items")

        ftp.quit()
        return True
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False
