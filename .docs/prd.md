# Product Requirements Document: LANbu Handy

**Version:** 0.3 (Consolidated for Repository)
**Date:** May 31, 2025

## 1. Introduction and Goals

### 1.1. Introduction
"LANbu Handy" is a Progressive Web Application (PWA) designed to enable users to slice 3D model files (initially `.3mf` and `.stl`) linked from the web and send them to their Bambu Labs printers operating in LAN-only mode. The application will be self-hostable within the user's home lab environment as a single Docker container.

### 1.2. Goals
* To restore core Bambu Handy app functionality (specifically, initiating prints from model files) for users whose printers are in LAN-only mode.
* Provide an intuitive, mobile-friendly PWA interface for a streamlined workflow from model URL to print initiation.
* Leverage an embedded instance of Bambu Studio CLI within its own container for slicing, ensuring users can utilize up-to-date slicing technology with minimal setup.
* Enable users to map their available AMS filaments to the requirements of the 3D model.
* Ensure all operations (post initial model download from the web) occur strictly within the user's local network.

### 1.3. Target Audience
Bambu Labs printer owners who:
* Prefer or require running their printers in LAN-only mode for privacy, security, or network policy reasons.
* Are comfortable with self-hosting applications within their home lab (e.g., using Docker).
* Desire a convenient mobile-first way to start prints without relying on cloud services for printer communication.

## 2. User Stories (MVP)

* **US001: Submit Model URL**: As a user, I want to paste a URL to a `.3mf` or `.stl` file into the PWA so that the system can retrieve the model for slicing.
* **US002: Printer Selection**: As a user with one or more Bambu printers on my LAN, I want the PWA to discover and allow me to select my target printer so that prints are sent to the correct device. (If only one, it can be pre-selected or configured).
* **US003: View Model's Filament Needs**: As a user, after submitting a `.3mf` model, I want to see the filament types and colors the model is designed for so I can prepare to map my AMS filaments.
* **US004: View AMS Filaments**: As a user, I want the PWA to query my selected printer's AMS and display the currently loaded filament types and colors in each slot so I know what's available.
* **US005: Automatic Filament Matching**: As a user, I want the PWA to automatically attempt to match the model's filament requirements with my available AMS filaments based on type and color to speed up setup.
* **US006: Manual Filament Assignment**: As a user, I want to be able to easily override or assign specific AMS filament slots to each part/color requirement of the model using a clear interface (e.g., dropdowns) so I have full control over filament selection.
* **US007: Select Build Plate**: As a user, I want to select the build plate type currently installed on my printer (e.g., Cool Plate, Textured PEI) from a predefined list so that the slicing is done with the correct plate adhesion and temperature settings.
* **US008: Retain Embedded Settings**: As a user, I want the system to respect and retain the print settings already embedded in the `.3mf` file, only applying my explicit overrides (like filament choice and build plate) so that prints generally match the designer's intent.
* **US009: Initiate Slicing**: As a user, once I've confirmed my settings (filaments, build plate), I want to tap a "Slice" button to start the slicing process via my self-hosted Bambu Studio.
* **US010: Slicing Feedback**: As a user, I want to see a visual indication that slicing is in progress and receive confirmation when it's complete, or see an error message if it fails, so I know the status.
* **US011: Initiate Print**: As a user, after successful slicing, I want to tap a "Print" button to send the sliced job to my selected printer and start the print.
* **US012: Print Initiation Feedback**: As a user, I want to receive confirmation that the print job has been successfully sent and started on the printer, or an error message if it fails, so I know if I can walk away.
* **US013: Clear Error Handling**: As a user, if any step fails (model download, printer communication, slicing, sending print), I want to see a clear, understandable error message so I can attempt to resolve the issue.
* **US014: Access PWA on LAN**: As a user, I want to access the PWA from my mobile browser while on my home Wi-Fi by navigating to its self-hosted address.

## 3. System Architecture (High-Level)

* **PWA Frontend**:
    * Built with modern web technologies (HTML, CSS, JavaScript, and a framework like Vue, React, or Svelte).
    * Responsible for all user interaction, displaying information, and making requests to the backend service.
    * Runs in the user's browser on a mobile device (or desktop) connected to the home LAN.
    * Served directly by the Backend Service.
* **Backend Service (Homelab Hosted - Single Docker Container)**:
    * A single Docker container running a lightweight service (e.g., Python with FastAPI/Flask, or Node.js with Express).
    * This container also includes the Bambu Studio Command Line Interface (CLI) and all its necessary dependencies.
    * Acts as an orchestrator:
        * Serves the PWA frontend files.
        * Receives API requests from the PWA.
        * Fetches the model file from the public URL.
        * Interacts with the Bambu printer's LAN API (e.g., using a library like `bambulabs_api` or direct MQTT/FTP calls) to:
            * Discover printers (if feasible).
            * Query AMS status.
            * Send G-code and print commands.
        * Interacts with the locally available Bambu Studio CLI (via subprocess calls within its own container) to:
            * Submit slicing jobs with specified parameters (input file, filament settings, plate type).
            * Retrieve the sliced output (G-code).
* **Bambu Labs Printer (LAN-Only Mode)**:
    * The target 3D printer, connected to the LAN and operating in its LAN-only mode.

**Conceptual Flow Diagram:**
`Mobile Browser (PWA) <-> LAN <-> Backend Service (Single Docker Container: [App Logic + Embedded Bambu Studio CLI])`
`Backend Service <-> LAN <-> Bambu Printer API`

## 4. Detailed Feature Specifications (MVP)

This section outlines the core features for the Minimum Viable Product. Detailed UI mockups and API specifications will be developed during the design and development phases.

### 4.1. Model Input & Retrieval
* **Description**: User provides a URL to a `.3mf` or `.stl` file. The system downloads and validates it.
* **Key Functionality**:
    * URL input field in PWA.
    * Backend downloads file from URL.
    * Validation (file type `.3mf`/`.stl`, reasonable size limit).
    * User feedback (downloading, success, error).
    * (Optional) Thumbnail extraction from `.3mf`.

### 4.2. Printer Discovery and Selection
* **Description**: User selects their target Bambu Lab printer on the LAN.
* **Key Functionality**:
    * Attempt auto-discovery of printers (mDNS or other LAN-based methods).
    * Allow manual IP address input as a fallback.
    * PWA displays selectable list or configured printer.
    * Store selected printer for the session.
    * (MVP Simplification) Start with manual IP configuration if discovery is complex.

### 4.3. AMS Filament Query & Mapping
* **Description**: Query AMS for loaded filaments and allow user to map them to model requirements.
* **Key Functionality**:
    * Backend queries printer's AMS (type, color, slot).
    * PWA displays model's filament needs (from `.3mf` metadata).
    * PWA displays available AMS filaments.
    * System attempts auto-matching based on type and color.
    * User interface (e.g., dropdowns) for manual assignment/override.

### 4.4. Build Plate Selection
* **Description**: User selects the current build plate on the printer.
* **Key Functionality**:
    * PWA displays dropdown of common Bambu Lab build plate types.
    * Selection passed to slicer. Defaults to `.3mf` specified plate or a common default.

### 4.5. Slicing Process (via Embedded Bambu Studio CLI)
* **Description**: User initiates slicing. Backend uses embedded CLI to process the model.
* **Key Functionality**:
    * "Slice" button in PWA.
    * Backend constructs and executes Bambu Studio CLI command as a local subprocess.
        * Respects settings from input `.3mf`.
        * Applies user overrides (filaments, build plate).
    * Progress indication and feedback (success/error).
    * Generated G-code is stored temporarily by the backend.

### 4.6. Print Initiation
* **Description**: User starts the print on the selected printer.
* **Key Functionality**:
    * "Print" button in PWA (enabled after successful slice).
    * Backend sends G-code file to printer (e.g., via FTP on LAN mode).
    * Backend sends print initiation command.
    * Feedback (success/error).

### 4.7. Error Handling & Feedback
* **Description**: Provide clear, user-friendly feedback for all operations.
* **Key Functionality**:
    * Informative messages in PWA for successes and failures at each step.
    * Detailed technical logs in the backend for troubleshooting.

## 5. Non-Functional Requirements

* **Usability**:
    * Workflow should be intuitive, aiming for ease comparable to Bambu Handy post-model selection.
    * PWA must be responsive and usable on common mobile screen sizes.
    * Clear visual hierarchy and timely feedback.
* **Performance**:
    * PWA should load quickly on the LAN.
    * File downloads and slicing should provide progress indication. Slicing time is dependent on model complexity and host machine, but the PWA should remain responsive.
    * API calls to printer/slicer should be reasonably fast.
* **Reliability**:
    * Stable communication with the embedded slicer and the printer's LAN API.
    * Graceful handling of intermittent network issues or unresponsive services with clear feedback.
* **Security**:
    * All communication between PWA, backend, slicer, and printer is confined to the user's LAN (except for the initial download of the model file from the user-provided public URL).
    * The backend should not expose unnecessary ports or services.
* **Maintainability**:
    * Backend and PWA code should be well-structured, commented, and easy to understand.
    * The Dockerfile for the all-in-one image must be carefully constructed and maintained to ensure both the backend application and the Bambu Studio CLI dependencies are correctly managed and updatable.
* **Testability**:
    * Backend: Unit tests for core logic (API interactions, CLI command generation, file handling).
    * PWA: UI interaction tests if feasible, or manual testing protocol.
    * Consider mock services/CLI responses for isolated backend testing.
* **Deployment**:
    * LANbu Handy will be deployable as a single Docker image, intended to be run as a single container via a simple `docker-compose.yml` service definition.
    * Users will not need to manage separate installations or configurations for Bambu Studio CLI; it will be fully embedded within the LANbu Handy Docker image.
    * Clear instructions will be provided for the `docker-compose.yml` setup and any necessary volume mappings.
    * **Characteristic**: Due to embedding Bambu Studio CLI, the LANbu Handy Docker image will be larger than a typical backend-only application image. This trade-off is accepted for maximal user deployment simplicity.
    * The Dockerfile itself will be part of the project, allowing users to build the image from source if desired, or pull a pre-built image from a container registry.
* **CI/CD (Continuous Integration/Continuous Deployment)**:
    * A basic CI pipeline (e.g., using GitHub Actions) should be set up to:
        * Automatically build the all-in-one Docker image upon code changes to the main branch.
        * Run linters and any automated tests.
        * Optionally, publish tagged releases of the Docker image to a container registry.

## 6. Future Considerations / Out of Scope for MVP

* Advanced real-time print monitoring (progress, temperatures, camera feed).
* Printer controls from PWA (pause, resume, cancel print).
* Object skipping during an active print.
* Support for additional 3D model file types (e.g., `.obj`, `.step`).
* Management of a library of user-defined print/slicer profiles.
* Basic model transformation tools in PWA (move, scale, rotate) before slicing.
* Print job queue management.
* User accounts/authentication (if PWA is exposed more broadly by user).
* Built-in secure remote access solution (beyond user-managed VPN/reverse proxy).
* Full Home Assistant add-on integration.
* Thumbnail generation for `.stl` files.
* More sophisticated printer discovery and management for multi-printer setups.
* Allowing users to select specific versions of Bambu Studio CLI if multiple are bundled or can be dynamically fetched.
