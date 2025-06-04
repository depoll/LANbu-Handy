# GitHub Copilot Workspace Instructions for LANbu Handy

## 1. Project Overview & Goal

**Project Name:** LANbu Handy

**Core Goal:** To develop a self-hosted Progressive Web Application (PWA) that allows users to:

1.  Input a URL to a 3D model file (`.stl`, `.3mf`).
2.  Download the model.
3.  Configure slicing parameters, including AMS filament selection (queried from the printer) and build plate type.
4.  Slice the model using an embedded instance of Bambu Studio CLI.
5.  Send the sliced G-code to a Bambu Lab printer operating in LAN-only mode and initiate the print.

The primary aim is to restore core Bambu Handy app functionality (initiating prints from models) for users who prefer or require their printers to be in LAN-only mode, without relying on cloud services for printer operation.

**Key User Experience:** Mobile-first, intuitive, and focused on a streamlined workflow from model URL to print start, all within the user's local network.

## 2. Key Reference Documents

Before starting work, please familiarize yourself with:

- **`.docs/prd.md`**: The Product Requirements Document contains detailed user stories, feature specifications, and non-functional requirements. This is the primary source of truth for _what_ to build.
- **`.docs/initial-development-plan.md`**: This document outlines the phased approach to development and breaks down features into larger tasks.
- **GitHub Issues**: Individual tasks are tracked as GitHub Issues. Please work on issues as assigned or prioritized. Each issue should correspond to a manageable chunk of work.

## 3. High-Level Architecture

LANbu Handy is designed as an "all-in-one" Dockerized application:

- **Single Docker Container**: The entire application (backend and PWA frontend) will run in a single Docker container.
- **Backend Service**:
  - **Preferred Tech**: Python with FastAPI. (Alternatively, Node.js with Express if strongly preferred for a specific reason).
  - **Responsibilities**:
    - Serve the PWA static files.
    - Provide a RESTful API for the PWA.
    - Orchestrate the workflow: model download, interaction with Bambu Studio CLI, communication with the printer's LAN API.
    - Embed and execute the **Bambu Studio CLI** as a local subprocess for slicing.
- **PWA Frontend**:
  - **Preferred Tech (for MVP)**: Vanilla JavaScript, HTML5, and CSS3 for simplicity and minimal overhead. Ensure good structure (e.g., modular JS). (A lightweight framework like Vue.js or Svelte could be considered for later enhancements if Vanilla JS becomes unwieldy).
  - **Responsibilities**: User interface, user input, API calls to the backend, displaying status and feedback.
- **Printer Communication**:
  - Via the Bambu Lab printer's LAN-only mode API (primarily MQTT for commands/status and FTP for file transfer).
  - Use existing Python libraries if suitable and reliable for LAN mode (e.g., `bambulabs_api` or similar), or implement direct protocol communication.

## 4. Development Guidelines & Conventions

- **Follow the Issues**: Implement features based on the descriptions and acceptance criteria in the assigned GitHub Issues.
- **Modularity**: Write modular and reusable code, especially for backend services (e.g., slicer interaction, printer communication) and PWA components.
- **Comments**: Add clear comments for complex logic, non-obvious decisions, and public API functions/methods.
- **Error Handling**: Implement robust error handling for all I/O operations, API calls, CLI interactions, and printer communications. Provide user-friendly error messages to the PWA.
- **Configuration**:
  - Printer IP address should initially be configurable via an environment variable for the Docker container (e.g., `BAMBU_PRINTER_IP`). The UI will later allow selection or manual input.
  - Avoid hardcoding configurable values.
- **Security**: While primarily for LAN use, validate all inputs from the PWA and ensure that file operations are handled securely (e.g., temporary file storage, path traversal).
- **Testing**:
  - Backend: Write unit tests for critical business logic (e.g., using `pytest`).
  - Focus on testable code.
- **PWA Design**:
  - Aim for a clean, simple, and intuitive mobile-first responsive design.
  - Prioritize ease of use for the core workflow.
- **Dockerfile**: Ensure the `Dockerfile` is clean, installs all dependencies (including Bambu Studio CLI correctly), and is optimized for size where possible (multi-stage builds later if appropriate).
- **Commit Messages**: Write clear and descriptive Git commit messages. Reference related issue numbers (e.g., `feat: Implement model download API (#11)`).

## 5. Tech Stack Preferences (Summary)

- **Backend**: Python 3.9+ with FastAPI.
- **Frontend (PWA)**: HTML5, CSS3, Vanilla JavaScript (ES6+).
- **Slicer**: Bambu Studio CLI (to be embedded in Docker).
- **Containerization**: Docker, Docker Compose.
- **CI/CD**: GitHub Actions (basic linting, Docker build initially).

## 6. What to Focus On / How Copilot Can Help Best

- **Implementing API Endpoints**: Based on the PRD and issue definitions for the FastAPI backend.
- **PWA Components**: Creating HTML structure, CSS styling, and JavaScript logic for UI elements and interactivity.
- **CLI Interaction**: Developing the Python wrapper to execute and manage the Bambu Studio CLI subprocess.
- **Printer Communication Logic**: Implementing FTP and MQTT communication with the Bambu printer based on its LAN protocol (or using a library).
- **Dockerfile Development**: Adding steps to install Bambu Studio CLI and other dependencies.
- **Boilerplate and Utility Functions**: Generating common utility functions, error handling structures, etc.
- **Unit Tests**: Writing unit tests for backend Python code.
- **Refactoring**: Helping to refactor code for clarity and modularity based on these instructions.

## 7. Things to Avoid / Anti-Patterns

- **Cloud Dependencies**: Do not introduce any cloud service dependencies for the core slicing or printing operations. The only external network access should be for downloading the 3D model from the user-provided public URL.
- **Overly Complex State Management (PWA MVP)**: For the MVP, keep frontend state management simple. Avoid complex libraries unless absolutely necessary.
- **Blocking Operations**: Ensure backend operations that might take time (downloading, slicing, printer communication) are handled asynchronously (FastAPI helps here) to prevent blocking the server or PWA.
- **Ignoring Errors**: Do not silently ignore errors from CLI execution or printer communication. They must be caught, logged, and reported appropriately to the user.
- **Hardcoding paths or sensitive info**: Use relative paths, environment variables, or configuration files.

By following these guidelines, Copilot Workspace can be a powerful assistant in building LANbu Handy efficiently and correctly.

## 8. Additional Guidelines

- Any new code must pass existing checks (CI, Linting, etc.) -- validate this before committing any change.
- As much as feasible, do your work within the dev container for the project and keep the dev container definition up to date as requirements change.
- When possible, include screenshots of any UI changes in the PR after implementing.
- If you change UI, provide screenshots of the changes in the PR.
