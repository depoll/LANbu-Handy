# v0.1.0 Tag Creation Documentation

This file documents the creation of the v0.1.0 tag for LANbu Handy's first release.

## Tag Details

- **Tag Name**: v0.1.0
- **Target Commit**: eebd34d56f58940d10b6e6ec56da3db073fb1b73
- **Commit Message**: [Phase 4] Add Automated Docker Image Publishing for Releases (#107)
- **Creation Date**: June 5, 2025
- **Tagger**: copilot-swe-agent[bot] <198982749+Copilot@users.noreply.github.com>

## Tag Message

```
v0.1.0 - First release of LANbu Handy

This is the first release of LANbu Handy, a self-hosted Progressive Web Application (PWA) 
that enables users to slice 3D model files and send them to Bambu Lab printers operating 
in LAN-only mode.

Key features in this release:
- URL to print workflow for 3D models (.3mf and .stl files)
- Local slicing using embedded Bambu Studio CLI
- LAN-only printer communication via MQTT and FTP
- Mobile-first responsive PWA interface
- AMS integration and filament mapping
- Build plate selection and configuration
- Docker-based deployment for self-hosting
```

## Release Process

1. Tag created on main branch commit eebd34d
2. Tag points to the commit containing automated Docker publishing workflow
3. When pushed, CI workflow will automatically:
   - Create GitHub release with title "Release v0.1.0"
   - Generate release notes and changelog
   - Build and publish Docker images as v0.1.0 and latest

## Verification Commands

```bash
git tag -l v0.1.0
git show v0.1.0
git show-ref --tags
```

This tag represents the completion of Phase 4 development and the first stable release of LANbu Handy.