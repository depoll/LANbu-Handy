# Serial Number Configuration Guide

LANbu Handy requires printer serial numbers for MQTT communication with Bambu Lab printers. This guide explains how to find and configure your printer's serial number.

## Why Serial Numbers Are Required

Bambu Lab printers use their serial number for MQTT communication topics in the format:

- `device/{serial_number}/request` for sending commands
- `device/{serial_number}/report` for receiving status

**Serial numbers are required** for MQTT communication to work properly. Without a configured serial number, the following features will not function:

- Print start commands
- AMS status queries
- Real-time printer status updates

## Finding Your Printer's Serial Number

### Method 1: Printer Display

1. On your Bambu printer's touchscreen, go to **Settings**
2. Navigate to **Device** or **About**
3. Look for **Serial Number** or **SN**
4. The serial number is typically 15 characters long (e.g., `01S00C123456789`)

### Method 2: Bambu Studio

1. Open Bambu Studio
2. Go to **Device** tab
3. Your printer's serial number will be displayed in the device list

### Method 3: Printer Label

- Check the label on your printer for the serial number
- It's usually printed on a sticker on the back or bottom of the printer

## Configuring Serial Numbers in LANbu Handy

### Via Web Interface

1. Open LANbu Handy in your web browser
2. Click **Configure** next to the printer selector
3. In the **Manual Configuration** section:
   - Enter your printer's **IP Address**
   - Enter the **Access Code** (if required)
   - **Enter the Serial Number** in the dedicated field (required for MQTT features)
   - Optionally save permanently for persistence across container restarts
4. Click **Set Active Printer** or **Save Printer Permanently**

### Via Environment Variables

Add the `serial_number` field to your `BAMBU_PRINTERS` environment variable:

```json
[
  {
    "name": "Bambu X1C",
    "ip": "192.168.1.100",
    "access_code": "12345678",
    "serial_number": "01S00C123456789"
  }
]
```

### Via Docker Compose

```yaml
services:
  lanbu-handy:
    image: lanbu-handy:latest
    environment:
      BAMBU_PRINTERS: |
        [
          {
            "name": "Bambu X1C",
            "ip": "192.168.1.100",
            "access_code": "12345678",
            "serial_number": "01S00C123456789"
          }
        ]
```

## Common Serial Number Patterns

Bambu Lab printers typically use these serial number patterns:

- **X1 Series**: `01S00C` + 9 digits (e.g., `01S00C123456789`)
- **P1 Series**: `01P00A` + 9 digits (e.g., `01P00A123456789`)
- **A1 Series**: `01A00B` + 9 digits (e.g., `01A00B123456789`)

## Troubleshooting

### MQTT Communication Issues

If you're experiencing MQTT communication problems:

1. **Verify Serial Number**: Double-check the serial number matches exactly what's shown on your printer
2. **Check Network**: Ensure LANbu Handy can reach your printer's IP address
3. **Access Code**: Verify the access code is correct (8-digit numeric code)
4. **Printer Settings**: Ensure your printer is in LAN-only mode and MQTT is enabled

### Serial Number Not Working

- Ensure there are no extra spaces or characters in the serial number
- Try copying the serial number directly from your printer's display
- Verify the serial number format matches your printer model (see patterns above)

### Logs and Debugging

- Check LANbu Handy logs for MQTT connection errors
- Look for errors about missing serial numbers
- Verify the MQTT topic format in debug logs

## Example Configuration

Here's a complete example of configuring a Bambu X1 Carbon:

```json
{
  "name": "My X1 Carbon",
  "ip": "192.168.1.100",
  "access_code": "12345678",
  "serial_number": "01S00C987654321"
}
```

This configuration will:

- Use MQTT topic `device/01S00C987654321/request` for commands
- Subscribe to `device/01S00C987654321/report` for status updates
- Enable proper AMS status queries and print commands

## Need Help?

If you're still having issues with serial number configuration:

1. Check your printer's documentation for the exact serial number location
2. Verify network connectivity between LANbu Handy and your printer
3. Review the application logs for specific error messages
4. Ensure the serial number is correctly entered (15 characters, matching your printer model)
