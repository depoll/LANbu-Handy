#!/usr/bin/env python3

"""
Mock Bambu Printer Service for E2E Testing

This script creates a mock MQTT and FTP service that simulates a Bambu Lab printer
in LAN-only mode for testing purposes.
"""

import json
import logging
import socket
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

# Mock printer configuration
MOCK_PRINTER_CONFIG = {
    "name": "Mock X1C Printer",
    "model": "X1C",
    "serial": "MOCK123456789",
    "ip": "192.168.1.100",
    "access_code": "12345678",
    "status": "idle",
    "bed_temp": 25,
    "nozzle_temp": 28,
    "ams_units": [
        {
            "id": 0,
            "slots": [
                {
                    "id": 0,
                    "filament_type": "PLA",
                    "color": "#FF0000",
                    "material_name": "Red PLA",
                    "remaining": 95,
                },
                {
                    "id": 1,
                    "filament_type": "PLA",
                    "color": "#00FF00",
                    "material_name": "Green PLA",
                    "remaining": 87,
                },
                {
                    "id": 2,
                    "filament_type": "PETG",
                    "color": "#0000FF",
                    "material_name": "Blue PETG",
                    "remaining": 76,
                },
                {
                    "id": 3,
                    "filament_type": "ABS",
                    "color": "#FFFFFF",
                    "material_name": "White ABS",
                    "remaining": 92,
                },
            ],
        }
    ],
}


class MockPrinterHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for mock printer API endpoints"""

    def do_GET(self):
        """Handle GET requests"""
        if self.path == "/api/status":
            self._send_json_response(
                {
                    "status": MOCK_PRINTER_CONFIG["status"],
                    "bed_temp": MOCK_PRINTER_CONFIG["bed_temp"],
                    "nozzle_temp": MOCK_PRINTER_CONFIG["nozzle_temp"],
                    "timestamp": datetime.now().isoformat(),
                }
            )
        elif self.path == "/api/ams":
            self._send_json_response({"ams_units": MOCK_PRINTER_CONFIG["ams_units"]})
        else:
            self._send_error_response(404, "Not Found")

    def do_POST(self):
        """Handle POST requests"""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        if self.path == "/api/print":
            try:
                data = json.loads(post_data.decode("utf-8"))
                filename = data.get("filename", "unknown.gcode")

                # Simulate print start
                print(f"📄 Mock printer: Starting print job: {filename}")
                MOCK_PRINTER_CONFIG["status"] = "printing"

                self._send_json_response(
                    {
                        "success": True,
                        "message": f"Print job {filename} started successfully",
                        "job_id": f"mock_job_{int(time.time())}",
                    }
                )
            except json.JSONDecodeError:
                self._send_error_response(400, "Invalid JSON")
        else:
            self._send_error_response(404, "Not Found")

    def _send_json_response(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_error_response(self, status, message):
        """Send error response"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

    def log_message(self, format, *args):
        """Custom log message format"""
        print(f"🌐 Mock HTTP: {format % args}")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Thread per request HTTP server"""

    pass


class MockMQTTBroker:
    """Simple mock MQTT broker for printer communication"""

    def __init__(self, host="localhost", port=1883):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None

    def start(self):
        """Start the mock MQTT broker"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.running = True

            print(f"📡 Mock MQTT broker started on {self.host}:{self.port}")

            while self.running:
                try:
                    client_socket, addr = self.socket.accept()
                    print(f"📡 Mock MQTT: Client connected from {addr}")

                    # Simple mock response
                    threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, addr),
                        daemon=True,
                    ).start()
                except OSError:
                    break

        except Exception as e:
            print(f"❌ Mock MQTT broker error: {e}")
        finally:
            if self.socket:
                self.socket.close()

    def _handle_client(self, client_socket, addr):
        """Handle MQTT client connection"""
        try:
            # Read client data
            data = client_socket.recv(1024)
            if data:
                print(f"📡 Mock MQTT: Received {len(data)} bytes from {addr}")

                # Send mock status update
                mock_status = json.dumps(
                    {
                        "print_job": {"state": "idle", "progress": 0},
                        "ams": MOCK_PRINTER_CONFIG["ams_units"],
                        "temperatures": {
                            "bed": MOCK_PRINTER_CONFIG["bed_temp"],
                            "nozzle": MOCK_PRINTER_CONFIG["nozzle_temp"],
                        },
                    }
                ).encode()

                client_socket.send(mock_status)

        except Exception as e:
            print(f"❌ Mock MQTT client error: {e}")
        finally:
            client_socket.close()

    def stop(self):
        """Stop the mock MQTT broker"""
        self.running = False
        if self.socket:
            self.socket.close()


class MockFTPServer:
    """Simple mock FTP server for file uploads"""

    def __init__(self, host="localhost", port=21):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None

    def start(self):
        """Start the mock FTP server"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.running = True

            print(f"📁 Mock FTP server started on {self.host}:{self.port}")

            while self.running:
                try:
                    client_socket, addr = self.socket.accept()
                    print(f"📁 Mock FTP: Client connected from {addr}")

                    threading.Thread(
                        target=self._handle_ftp_client,
                        args=(client_socket, addr),
                        daemon=True,
                    ).start()
                except OSError:
                    break

        except Exception as e:
            print(f"❌ Mock FTP server error: {e}")
        finally:
            if self.socket:
                self.socket.close()

    def _handle_ftp_client(self, client_socket, addr):
        """Handle FTP client connection"""
        try:
            # Send FTP welcome message
            client_socket.send(b"220 Mock FTP Server Ready\r\n")

            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break

                command = data.decode().strip()
                print(f"📁 Mock FTP: Command: {command}")

                if command.startswith("USER"):
                    client_socket.send(b"331 Password required\r\n")
                elif command.startswith("PASS"):
                    client_socket.send(b"230 User logged in\r\n")
                elif command.startswith("STOR"):
                    filename = command.split(" ", 1)[1] if " " in command else "unknown"
                    print(f"📁 Mock FTP: File upload: {filename}")
                    client_socket.send(b"226 Transfer complete\r\n")
                elif command == "QUIT":
                    client_socket.send(b"221 Goodbye\r\n")
                    break
                else:
                    client_socket.send(b"200 OK\r\n")

        except Exception as e:
            print(f"❌ Mock FTP client error: {e}")
        finally:
            client_socket.close()

    def stop(self):
        """Stop the mock FTP server"""
        self.running = False
        if self.socket:
            self.socket.close()


def main():
    """Main function to start all mock services"""
    print("🚀 Starting Mock Bambu Printer Services...")
    print(
        f"📊 Mock Printer: {MOCK_PRINTER_CONFIG['name']} "
        f"({MOCK_PRINTER_CONFIG['model']})"
    )
    print(f"📍 IP Address: {MOCK_PRINTER_CONFIG['ip']}")
    print(f"🔑 Access Code: {MOCK_PRINTER_CONFIG['access_code']}")
    print()

    # Start HTTP server for API endpoints
    http_server = ThreadedHTTPServer(("localhost", 8081), MockPrinterHTTPHandler)
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()
    print("🌐 Mock HTTP API server started on http://localhost:8081")

    # Start MQTT broker
    mqtt_broker = MockMQTTBroker("localhost", 1883)
    mqtt_thread = threading.Thread(target=mqtt_broker.start, daemon=True)
    mqtt_thread.start()

    # Start FTP server
    ftp_server = MockFTPServer("localhost", 2121)  # Use non-privileged port
    ftp_thread = threading.Thread(target=ftp_server.start, daemon=True)
    ftp_thread.start()

    print()
    print("🎯 Mock Services Summary:")
    print("   📡 MQTT Broker: localhost:1883")
    print("   📁 FTP Server: localhost:2121")
    print("   🌐 HTTP API: http://localhost:8081")
    print()
    print("🧪 Test endpoints:")
    print("   GET  http://localhost:8081/api/status")
    print("   GET  http://localhost:8081/api/ams")
    print("   POST http://localhost:8081/api/print")
    print()
    print("Press Ctrl+C to stop all services...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping mock services...")
        http_server.shutdown()
        mqtt_broker.stop()
        ftp_server.stop()
        print("✅ All mock services stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
