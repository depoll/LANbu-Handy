# Router Integration Guide

This directory contains the final four routers extracted from main.py:

## Routers Created

### 1. Jobs Router (`jobs.py`)
**Endpoints:**
- `POST /api/job/start-basic` - Complete workflow orchestration (download, slice, upload, print)
- `POST /api/job/start-print` - Start print with existing G-code file
- `POST /api/job/send-to-printer` - Send G-code to printer without starting print

**Dependencies:**
- `JobOrchestration` service functions (download_model_step, slice_model_step, etc.)
- `ModelService` for plate estimate extraction
- `PrinterService` for printer operations
- Config service for printer management

### 2. Filaments Router (`filaments.py`)
**Endpoints:**
- `POST /api/filament/match` - Match filament requirements with AMS status

**Dependencies:**
- `FilamentMatchingService` for sophisticated filament matching logic
- Internal service models for conversion between API and service layers

### 3. G-code Router (`gcode.py`)
**Endpoints:**
- `GET /api/gcode/download/{file_name}` - Download generated G-code files

**Dependencies:**
- `get_gcode_output_dir()` utility function
- File validation and security checks

### 4. Uploads Router (`uploads.py`)
**Endpoints:**
- `GET /api/upload/progress/{upload_id}` - Track upload progress for file operations

**Dependencies:**
- `UploadProgressService` for progress tracking

## Integration Steps

To integrate these routers into main.py:

### 1. Import the routers
```python
from app.routers import jobs, filaments, gcode, uploads
```

### 2. Include routers in FastAPI app
```python
# Add after app creation
app.include_router(jobs.router)
app.include_router(filaments.router)
app.include_router(gcode.router)  
app.include_router(uploads.router)
```

### 3. Inject service dependencies
```python
# After service initialization
jobs.set_services(model_service, printer_service)
filaments.set_service(filament_matching_service)
uploads.set_service(upload_progress_service)
# gcode router doesn't need service injection
```

### 4. Remove old endpoints from main.py
Remove these endpoints from main.py:
- `@app.post("/api/job/start-basic")` and `start_basic_job()`
- `@app.post("/api/job/start-print")` and `start_print_job()`
- `@app.post("/api/job/send-to-printer")` and `send_to_printer()`
- `@app.post("/api/filament/match")` and `match_filaments()`
- `@app.get("/api/gcode/download/{file_name}")` and `download_gcode()`
- `@app.get("/api/upload/progress/{upload_id}")` and `get_upload_progress()`

## Service Dependencies Summary

Each router requires specific service injections:

**Jobs Router:**
- ModelService instance
- PrinterService instance  
- Config (automatically available via get_config())

**Filaments Router:**
- FilamentMatchingService instance

**Uploads Router:**  
- UploadProgressService instance

**G-code Router:**
- No service dependencies (uses utility functions only)

## Error Handling

All routers maintain the same error handling patterns as the original main.py:
- HTTP exceptions are re-raised as-is
- Internal exceptions are caught and converted to 500 errors with descriptive messages
- Logging is preserved for debugging

## Response Models

All routers include the necessary Pydantic models for request/response validation:
- JobStartRequest/JobStartResponse
- FilamentMatchRequest/FilamentMatchResponse  
- No additional models needed for gcode and uploads (simple dict responses)

## Security Features

- Path traversal protection in G-code download
- File validation and directory restrictions
- Input validation via Pydantic models
- Proper HTTP status codes for different error conditions