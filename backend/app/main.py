"""
LANbu Handy - Backend Main Application

FastAPI application for LANbu Handy - a self-hosted PWA for slicing and printing
3D models to Bambu Lab printers in LAN-only mode.
"""

from fastapi import FastAPI

app = FastAPI(
    title="LANbu Handy",
    description="Self-hosted PWA for slicing and printing 3D models to Bambu Lab printers in LAN-only mode",
    version="0.1.0"
)


@app.get("/")
async def read_root():
    """
    Root endpoint returning a simple hello world response.
    """
    return {"message": "Hello World", "app": "LANbu Handy", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy"}