# LANbu Handy Release Notes

## v0.1.0 - First Release (June 2025)

This is the first release of LANbu Handy, marking a significant milestone in providing LAN-only 3D printing capabilities for Bambu Lab printers.

### What's New

**Core Features:**
- **URL to Print Workflow**: Input a URL to .3mf or .stl files and start printing directly
- **Local Slicing**: Embedded Bambu Studio CLI for reliable, up-to-date slicing
- **LAN-Only Operation**: Complete printer control without cloud dependencies
- **Mobile-First PWA**: Responsive Progressive Web Application optimized for mobile devices
- **AMS Integration**: Query AMS status and map filaments to model requirements
- **Build Plate Selection**: Support for all Bambu Lab build plate types
- **Docker Deployment**: Self-hosted single-container deployment

**Technical Highlights:**
- React 19 + TypeScript frontend with Vite build system
- FastAPI Python backend with comprehensive test coverage
- MQTT and FTP communication for LAN-only printer control
- Automated Docker image publishing and GitHub releases
- Comprehensive testing suite with E2E testing guides

### Getting Started

```bash
git clone https://github.com/depoll/LANbu-Handy.git
cd LANbu-Handy
docker compose up -d
```

Access the PWA at `http://[your-server-ip]:8080`

### Documentation

- [README.md](README.md) - Complete setup and usage guide
- [DEVELOPER_NOTES.md](DEVELOPER_NOTES.md) - Architecture and development guide
- [.docs/prd.md](.docs/prd.md) - Product requirements and specifications

### Docker Images

- `ghcr.io/depoll/lanbu-handy:v0.1.0`
- `ghcr.io/depoll/lanbu-handy:latest`

### Known Limitations

- Single printer support per container instance (multi-printer configuration available)
- Large model downloads (>100MB) may require increased timeout settings
- Bambu Studio CLI requires x86_64 architecture (ARM support planned)

### Next Steps

See the [roadmap in README.md](README.md#roadmap) for planned enhancements including:
- Enhanced printer discovery
- Advanced slicing configuration options
- Performance optimizations
- Extended testing coverage

---

For detailed changes, see the [commit history](https://github.com/depoll/LANbu-Handy/commits/v0.1.0).