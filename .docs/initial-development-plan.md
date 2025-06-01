# LANbu Handy - Initial Development Plan

**Version:** 1.0
**Date:** June 1, 2025
**Related PRD Version:** 0.3

## 1. Introduction

This document outlines the initial development plan for "LANbu Handy," a PWA for slicing and printing 3D models on Bambu Lab printers in LAN-only mode. This plan breaks the project into manageable phases, detailing the key tasks and objectives for each. It is intended to be used in conjunction with the Product Requirements Document (PRD).

The primary goal is to iteratively build the Minimum Viable Product (MVP) as defined in the PRD, focusing on delivering core functionality first and then layering on enhancements and polish.

## 2. Technology Considerations (Initial Thoughts)

* **Backend**: A Python-based framework (e.g., FastAPI or Flask) or a Node.js framework (e.g., Express.js) are good candidates due to their widespread support, extensive libraries (especially for web requests, file handling, and interacting with system processes), and suitability for AI agent development.
* **PWA Frontend**: A modern JavaScript framework like Vue.js, React, or Svelte, or even vanilla JavaScript with careful structuring, can be used. The choice may depend on desired reactivity and component structure.
* **Bambu Studio CLI Interaction**: The backend will execute the Bambu Studio CLI as a subprocess. Research will be needed to determine the optimal way to install and call the CLI within the Docker container.
* **Printer Communication**: Utilize a Python or Node.js library for Bambu Lab printers (like `bambulabs_api` if suitable and mature for LAN mode) or implement direct communication via MQTT/FTP as per Bambu Lab's LAN mode protocol.

## 3. Development Phases

### Phase 0: Project Setup & Foundation

* **Goal**: Establish the basic project structure, development environment, and CI/CD pipeline.
* **Key Tasks**:
    1.  **Repository Setup**:
        * Initialize Git repository.
        * Add `prd.md` and this `initial-development-plan.md`.
        * Create basic `.gitignore` file.
    2.  **Project Structure**:
        * Create top-level directories for `backend` and `pwa` (or `frontend`).
        * Basic boilerplate for a chosen backend framework (e.g., FastAPI "hello world").
        * Basic boilerplate for a chosen PWA framework/setup (e.g., `create-vite` for Vue/React/Svelte, or simple HTML/JS structure).
    3.  **Dockerfile (Initial Version)**:
        * Create `Dockerfile` for the all-in-one image.
        * It should set up the chosen backend language environment.
        * Include a placeholder or initial attempt to install/include Bambu Studio CLI (this will be refined in Phase 1).
        * Configure the backend to serve the PWA static files.
    4.  **Docker Compose**:
        * Create `docker-compose.yml` to build and run the single "LANbu Handy" service.
        * Include basic port mapping and any initial volume mounts.
    5.  **Basic CI Pipeline**:
        * Set up GitHub Actions (or similar CI service).
        * Initial workflow to:
            * Lint backend code (e.g., Black, Flake8 for Python; ESLint for Node.js).
            * Lint PWA code.
            * Attempt to build the Docker image (catches Dockerfile errors).
    6.  **"Hello World" End-to-End**:
        * Backend: Create a simple API endpoint (e.g., `/api/status`).
        * PWA: Fetch from this endpoint and display the result.
        * Confirm the PWA is served by the backend and can communicate with it when run via Docker Compose.
* **Milestone**: A runnable Docker container serving a basic PWA that can make an API call to its backend. CI pipeline is green.

### Phase 1: Core Slicing & Printing Backbone (Backend Heavy)

* **Goal**: Implement the absolute core functionality: download a model, slice it with defaults, and send it to a (pre-configured) printer.
* **Key Tasks**:
    1.  **Bambu Studio CLI Integration (Backend)**:
        * Finalize the method for installing Bambu Studio CLI into the Docker image. Ensure it's executable by the backend.
        * Develop a robust wrapper function in the backend to call the Bambu Studio CLI as a subprocess, capture its output/errors, and manage input/output files.
    2.  **Model Download & Prep (Backend)**:
        * Create API endpoint (e.g., `/api/prepare-model`) that accepts a model URL.
        * Implement logic to download the file from the URL.
        * Validate file type (`.3mf`/`.stl`) and size.
        * Store the file temporarily where the CLI can access it.
    3.  **Basic Slicing (Backend)**:
        * Extend the CLI wrapper to perform a basic slice operation on the downloaded model, using default print/filament profiles embedded in Bambu Studio CLI for now.
        * The output G-code should be saved to a known temporary location.
    4.  **Basic Printer Communication (Backend)**:
        * Implement functions to send a G-code file to a Bambu Lab printer at a **manually configured IP address** using the LAN mode protocol (e.g., FTP).
        * Implement a function to send the command to start printing the uploaded file.
        * Initial error handling for printer communication failures.
    5.  **Minimal PWA Interface**:
        * Simple input field for the model URL.
        * A single "Slice and Print" button.
        * Basic feedback display (e.g., "Downloading...", "Slicing...", "Printing...", "Error: [message]").
    6.  **Configuration**:
        * Allow printer IP to be configured via an environment variable for the Docker container.
* **Milestone**: Ability to provide a URL to a simple `.stl` file via the PWA and have it sliced with default settings and printed on a pre-configured printer. Basic status updates shown in PWA.

### Phase 2: Enhanced Slicing Configuration & AMS Integration

* **Goal**: Allow user to select filaments from AMS and choose a build plate, respecting `.3mf` settings.
* **Key Tasks**:
    1.  **AMS Query (Backend)**:
        * Implement functionality to query the selected printer's AMS status (filament types, colors, slots) via its LAN API.
        * Expose this information via a new API endpoint.
    2.  **`.3mf` Parsing (Backend - Optional/Simplified for MVP)**:
        * If `.3mf` files contain specific filament assignments, investigate how to extract this. For MVP, we might assume a simpler model where user assigns filaments to logical extruders/colors.
        * Focus on how the CLI handles filament assignments within `.3mf` or via overrides.
    3.  **Filament Mapping Logic (Backend)**:
        * Develop logic for auto-matching model filament needs (either generic or from `.3mf`) with available AMS filaments.
        * Update the slicing API endpoint to accept user's filament mapping choices and build plate selection.
    4.  **Update CLI Slicing Call (Backend)**:
        * Modify the Bambu Studio CLI call to include parameters for:
            * Selected filaments from AMS.
            * Selected build plate type.
            * Ensuring it respects other settings from an input `.3mf` file if provided.
    5.  **PWA UI for Configuration**:
        * Display AMS filament status fetched from backend.
        * If applicable, display model's intended filaments.
        * Provide UI (e.g., dropdowns) for the user to map available AMS filaments to the print.
        * Add UI to select the build plate type.
        * Separate "Slice" and "Print" buttons in the PWA workflow.
    6.  **Feedback**:
        * Improved PWA feedback for each step (AMS query, slicing, print initiation).
* **Milestone**: User can specify AMS filaments and build plate, slice the model with these settings, and then initiate the print. Settings from `.3mf` files are largely respected.

### Phase 3: Printer Discovery & UX Polish

* **Goal**: Improve printer management and overall user experience with better feedback and error handling.
* **Key Tasks**:
    1.  **Printer Discovery/Selection (Backend & PWA)**:
        * Investigate and implement printer discovery on the LAN (e.g., mDNS if available/reliable for Bambu printers).
        * If discovery is implemented, PWA UI to list and select discovered printers.
        * Robust manual IP address input and management in the PWA as a primary or fallback method.
        * Backend API endpoints to support printer selection/management.
    2.  **Enhanced PWA Feedback**:
        * Implement clearer progress indicators for long operations (download, slicing).
        * More detailed and user-friendly success and error messages.
        * Visual cues for application state.
    3.  **Session Persistence (PWA - Optional)**:
        * Consider persisting the selected printer IP or other common settings in browser local storage for convenience.
    4.  **Comprehensive Error Handling**:
        * Review and improve error handling across all backend and PWA components.
        * Ensure graceful failure and clear reporting to the user.
    5.  **Code Refinement & Structure**:
        * Refactor code for clarity and maintainability in both backend and PWA.
* **Milestone**: A more polished and robust application. Printer selection is user-friendly. Errors are handled gracefully.

### Phase 4: Testing, Documentation & Release Preparation

* **Goal**: Ensure the application is stable, well-documented, and ready for an initial release/wider personal use.
* **Key Tasks**:
    1.  **Testing**:
        * **Unit Tests (Backend)**: Increase coverage for backend logic, API endpoints, CLI interaction, printer communication.
        * **Integration Tests**: Test interactions between PWA and backend, and backend with CLI/printer (can be semi-automated).
        * **Manual End-to-End Testing**: Thoroughly test all user stories from the PRD on various devices/browsers on the LAN. Test with different `.stl` and `.3mf` files.
    2.  **Documentation**:
        * **User Guide (`README.md` or separate `USAGE.md`)**:
            * How to configure and run LANbu Handy using Docker Compose.
            * How to use the PWA features.
            * Troubleshooting common issues.
        * **Developer Notes**: Document key aspects of the codebase, CLI interaction, and printer API usage for future maintenance.
    3.  **Dockerfile Optimization**:
        * Minimize Docker image size where possible (multi-stage builds, removing unnecessary build dependencies).
        * Ensure security best practices for the Docker image.
    4.  **CI/CD Pipeline Enhancements**:
        * Automate building and pushing tagged release images to a container registry (e.g., Docker Hub, GitHub Container Registry).
    5.  **Final Review**:
        * Review against PRD to ensure all MVP features are met.
        * Performance check.
* **Milestone**: LANbu Handy MVP is stable, documented, and easily deployable for users.

## 4. Iteration and Future Development

This plan covers the MVP. Future development will be guided by the "Future Considerations" section of the PRD and user feedback, potentially including:
* Advanced print monitoring.
* Full Home Assistant integration.
* Support for more file types.

This development plan should be a living document and can be adjusted as the project progresses and new information or priorities emerge.
