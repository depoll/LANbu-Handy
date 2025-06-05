# Printer Management and Persistent Storage

LANbu Handy now supports persistent printer configurations that survive container restarts and upgrades. This document explains how to use the new printer management features.

## Features

- **Persistent Storage**: Save printer configurations permanently to survive container restarts
- **Hybrid Configuration**: Combines environment variables and persistent storage
- **User-Friendly UI**: Manage printers directly from the web interface
- **Automatic Discovery**: Find printers on your network automatically
- **Flexible Storage**: Choose per-printer whether to save temporarily or permanently

## Configuration Methods

### 1. Persistent Storage (New)

#### Enable Persistent Storage

To enable persistent storage, uncomment the volume mount in your `docker-compose.yml`:

```yaml
services:
  lanbuhandy:
    # ... other configuration
    volumes:
      # Uncomment the line below to enable persistent storage across container upgrades
      - ./config:/app/data
```

This creates a `config` directory in your LANbu Handy installation folder where printer configurations are stored.

#### Add Printers via UI

1. Open LANbu Handy in your browser
2. Look for the printer configuration section
3. Click "Configure" to expand the printer selector
4. Either:
   - Use "Scan Network" to discover printers automatically
   - Enter printer details manually
5. **Important**: Check "Save permanently" to persist the printer across restarts
6. Click "Save Printer Permanently" or "Set Active Printer"

#### Managing Persistent Printers

- **View all printers**: The printer selector shows all configured printers with badges indicating their storage type
- **Temporary printers**: Show "Session" badge - lost on restart
- **Persistent printers**: Show "Saved" badge - survive restarts
- **Environment printers**: Configured via environment variables (always persistent)

### 2. Environment Variables (Existing)

You can still configure printers via environment variables. These take precedence if they have the same IP as a persistent printer.

#### New JSON Format (Recommended)
```bash
BAMBU_PRINTERS='[
  {
    "name": "Living Room X1C",
    "ip": "192.168.1.100", 
    "access_code": "12345678"
  },
  {
    "name": "Garage A1 mini",
    "ip": "192.168.1.101",
    "access_code": "87654321"
  }
]'
```

#### Legacy Format (Still Supported)
```bash
BAMBU_PRINTER_IP=192.168.1.100
BAMBU_PRINTER_ACCESS_CODE=12345678
```

## Storage Priority

LANbu Handy loads printers in this order:

1. **Persistent storage** (`/app/data/printers.json`)
2. **Environment variables** (only if IP doesn't conflict with persistent storage)

This means persistent storage takes precedence over environment variables for the same IP address.

## File Structure

When using persistent storage, printer configurations are stored in JSON format:

```json
{
  "version": "1.0",
  "printers": [
    {
      "name": "My X1 Carbon",
      "ip": "192.168.1.100",
      "access_code": "12345678"
    }
  ]
}
```

## API Endpoints

The following new API endpoints are available for managing persistent printers:

- `POST /api/printers/add` - Add a printer (temporary or persistent)
- `POST /api/printers/remove` - Remove a printer from persistent storage
- `GET /api/printers/persistent` - List all persistent printers
- `GET /api/config` - Get configuration (updated with persistence info)

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PRINTER_CONFIG_FILE` | Path to persistent printer config file | `/app/data/printers.json` |
| `BAMBU_PRINTERS` | JSON array of printer configurations | `""` |
| `BAMBU_PRINTER_IP` | Legacy single printer IP | `""` |
| `BAMBU_PRINTER_ACCESS_CODE` | Legacy single printer access code | `""` |

### Docker Compose Configuration

```yaml
services:
  lanbuhandy:
    image: ghcr.io/depoll/lanbu-handy:latest
    platform: linux/amd64
    ports:
      - '8080:8000'
    restart: unless-stopped
    volumes:
      # Enable persistent storage (recommended)
      - ./config:/app/data
    environment:
      # Optional: Persistent storage config file path
      - PRINTER_CONFIG_FILE=/app/data/printers.json
      
      # Optional: Environment-based printer configuration  
      - BAMBU_PRINTERS=${BAMBU_PRINTERS:-}
      - BAMBU_PRINTER_IP=${BAMBU_PRINTER_IP:-}
      - BAMBU_PRINTER_ACCESS_CODE=${BAMBU_PRINTER_ACCESS_CODE:-}
```

## Migration Guide

### From Environment Variables Only

If you currently configure printers via environment variables:

1. Add the volume mount to your `docker-compose.yml`
2. Restart the container
3. Your environment printers will still work
4. Use the UI to add new printers with persistent storage
5. Gradually migrate to persistent storage for easier management

### Backup and Restore

To backup your printer configurations:

1. Copy the `config/printers.json` file
2. Store it safely

To restore:

1. Replace `config/printers.json` with your backup
2. Restart the container

## Troubleshooting

### Printers Not Persisting

- Check if the volume mount is configured: `- ./config:/app/data`
- Verify the "Save permanently" checkbox is checked when adding printers
- Check container logs for storage errors

### Permission Issues

If you get permission errors:

```bash
# Fix ownership of the config directory
sudo chown -R 1000:1000 ./config
```

### Configuration Conflicts

- Persistent printers override environment printers with the same IP
- Check `GET /api/config` to see which printers are loaded and their source
- Remove conflicting environment variables if needed

## Best Practices

1. **Use Persistent Storage**: Enable the volume mount for easier management
2. **Backup Configurations**: Regularly backup `config/printers.json`
3. **Test Before Production**: Verify printer connectivity after configuration
4. **Document Access Codes**: Keep access codes secure and documented
5. **Monitor Logs**: Check container logs for any configuration issues

## Security Notes

- Access codes are stored in plain text in the configuration file
- Ensure proper file permissions on the config directory
- Consider using environment variables for sensitive production deployments
- The config file is not encrypted - protect access to the host system