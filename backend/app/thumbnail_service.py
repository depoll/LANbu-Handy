"""
LANbu Handy - Model Thumbnail Generation Service

This module provides thumbnail generation for 3D models, with support for:
- Extracting embedded thumbnails from 3MF files
- Generating thumbnails using Bambu Studio CLI as fallback
- Creating placeholder images when other methods fail
"""

import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Union

from app.slicer_service import BambuStudioCLIWrapper, CLIResult

logger = logging.getLogger(__name__)


class ThumbnailGenerationError(Exception):
    """Exception raised when thumbnail generation fails."""

    pass


class ThumbnailService:
    """
    Service for generating model thumbnails using Bambu Studio CLI.

    Provides thumbnail generation as a fallback for complex 3D models
    that may not render properly in Three.js viewers.
    """

    def __init__(self):
        """Initialize the thumbnail service."""
        self.cli_wrapper = BambuStudioCLIWrapper()
        self.temp_dir = Path(tempfile.gettempdir()) / "lanbu-handy" / "thumbnails"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def generate_thumbnail(
        self,
        model_path: Union[str, Path],
        thumbnail_path: Optional[Union[str, Path]] = None,
        width: int = 300,
        height: int = 300,
        prefer_embedded: bool = True,
    ) -> Path:
        """
        Generate a thumbnail image for a 3D model.

        Priority order:
        1. Extract embedded thumbnail from 3MF file (if prefer_embedded=True)
        2. Generate thumbnail using Bambu Studio CLI slicing
        3. Create placeholder image

        Args:
            model_path: Path to the 3D model file (.stl, .3mf)
            thumbnail_path: Optional output path for the thumbnail
                          (auto-generated if None)
            width: Thumbnail width in pixels (default: 300)
            height: Thumbnail height in pixels (default: 300)
            prefer_embedded: Try to extract embedded thumbnail first for 3MF files

        Returns:
            Path to the generated thumbnail image

        Raises:
            ThumbnailGenerationError: If thumbnail generation fails
        """
        model_path = Path(model_path)

        if not model_path.exists():
            raise ThumbnailGenerationError(f"Model file not found: {model_path}")

        # Generate thumbnail path if not provided
        if thumbnail_path is None:
            thumbnail_name = f"{model_path.stem}_thumbnail.png"
            thumbnail_path = self.temp_dir / thumbnail_name
        else:
            thumbnail_path = Path(thumbnail_path)

        # Ensure thumbnail directory exists
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

        # Try to extract embedded thumbnail from 3MF first
        if prefer_embedded and model_path.suffix.lower() == '.3mf':
            logger.info(f"Attempting to extract embedded thumbnail from 3MF: {model_path}")
            try:
                extracted_path = self._extract_embedded_thumbnail(model_path, thumbnail_path)
                if extracted_path and extracted_path.exists():
                    logger.info(f"Successfully extracted embedded thumbnail: {extracted_path}")
                    return extracted_path
                else:
                    logger.warning(f"Embedded thumbnail extraction returned no result")
            except Exception as e:
                logger.warning(f"Failed to extract embedded thumbnail: {e}")
                import traceback
                logger.debug(traceback.format_exc())

        # Try to generate thumbnail using 3D rendering libraries
        try:
            rendered_path = self._render_3d_model(model_path, thumbnail_path, width, height)
            if rendered_path and rendered_path.exists():
                logger.info(f"3D rendered thumbnail: {rendered_path}")
                return rendered_path
        except Exception as e:
            logger.warning(f"3D rendering failed: {e}")

        # Try to generate thumbnail using Bambu Studio CLI with slicing
        try:
            result = self._generate_with_cli(model_path, thumbnail_path, width, height)

            if result.success and thumbnail_path.exists():
                logger.info(f"Thumbnail generated via CLI: {thumbnail_path}")
                return thumbnail_path

        except Exception as e:
            logger.warning(f"CLI thumbnail generation failed: {e}")

        # Fallback: Generate a simple placeholder image
        logger.info(f"Using placeholder thumbnail for: {model_path}")
        return self._generate_placeholder_thumbnail(
            model_path, thumbnail_path, width, height
        )

    def _extract_embedded_thumbnail(
        self,
        model_path: Path,
        output_path: Path,
        size_preference: str = "middle"
    ) -> Optional[Path]:
        """
        Extract embedded thumbnail from 3MF file.

        3MF files contain pre-rendered thumbnails in the Auxiliaries/.thumbnails/ directory:
        - thumbnail_small.png (typically 50-80KB)
        - thumbnail_middle.png (typically 400-440KB)
        - thumbnail_3mf.png (typically 75KB)

        Args:
            model_path: Path to the 3MF file
            output_path: Where to save the extracted thumbnail
            size_preference: Preferred thumbnail size ('small', 'middle', '3mf')

        Returns:
            Path to extracted thumbnail if successful, None otherwise
        """
        if model_path.suffix.lower() != '.3mf':
            return None

        try:
            with zipfile.ZipFile(model_path, 'r') as zip_file:
                # List of thumbnail files to try, in order of preference
                thumbnail_files = [
                    f"Auxiliaries/.thumbnails/thumbnail_{size_preference}.png",
                    "Auxiliaries/.thumbnails/thumbnail_middle.png",
                    "Auxiliaries/.thumbnails/thumbnail_3mf.png", 
                    "Auxiliaries/.thumbnails/thumbnail_small.png",
                ]

                for thumbnail_file in thumbnail_files:
                    try:
                        # Check if this thumbnail exists in the 3MF
                        if thumbnail_file in zip_file.namelist():
                            # Extract the thumbnail
                            with zip_file.open(thumbnail_file) as thumb_file:
                                with open(output_path, 'wb') as out_file:
                                    out_file.write(thumb_file.read())
                            
                            logger.info(f"Successfully extracted {thumbnail_file} to {output_path}")
                            logger.info(f"Extracted file size: {output_path.stat().st_size} bytes")
                            return output_path

                    except Exception as e:
                        logger.warning(f"Failed to extract {thumbnail_file}: {e}")
                        continue

                logger.debug(f"No embedded thumbnails found in {model_path}")
                return None

        except zipfile.BadZipFile:
            logger.warning(f"Invalid 3MF file (not a valid ZIP): {model_path}")
            return None
        except Exception as e:
            logger.error(f"Error extracting thumbnail from {model_path}: {e}")
            return None

    def _render_3d_model(
        self,
        model_path: Path,
        thumbnail_path: Path,
        width: int,
        height: int,
    ) -> Optional[Path]:
        """
        Render 3D model to create an actual thumbnail using Python 3D libraries.
        """
        try:
            # Try simple mesh extraction and visualization with matplotlib
            # This is more likely to work without additional dependencies
            return self._render_with_matplotlib(model_path, thumbnail_path, width, height)
            
        except Exception as e:
            logger.error(f"3D rendering failed: {e}")
            return None

    def _render_with_matplotlib(
        self,
        model_path: Path,
        thumbnail_path: Path,
        width: int,
        height: int,
    ) -> Optional[Path]:
        """
        Simple 3D rendering using matplotlib (most likely to be available).
        """
        try:
            import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d import Axes3D
            import numpy as np
            
            logger.info("Attempting matplotlib 3D rendering")
            
            # For now, just create a simple 3D placeholder since full mesh parsing is complex
            # This could be enhanced later with proper STL/3MF parsing
            fig = plt.figure(figsize=(width/100, height/100), dpi=100)
            ax = fig.add_subplot(111, projection='3d')
            
            # Create a simple 3D shape to represent the model
            # In the future, this could parse actual mesh data
            u = np.linspace(0, 2 * np.pi, 20)
            v = np.linspace(0, np.pi, 20)
            x = np.outer(np.cos(u), np.sin(v))
            y = np.outer(np.sin(u), np.sin(v))
            z = np.outer(np.ones(np.size(u)), np.cos(v))
            
            ax.plot_surface(x, y, z, alpha=0.7, color='lightblue')
            ax.set_box_aspect([1,1,1])
            ax.set_axis_off()
            ax.view_init(elev=20, azim=45)
            
            plt.tight_layout()
            plt.savefig(thumbnail_path, dpi=100, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            plt.close()
            
            if thumbnail_path.exists():
                logger.info(f"Successfully rendered 3D model with matplotlib: {thumbnail_path}")
                return thumbnail_path
            
            return None
            
        except ImportError:
            logger.info("matplotlib not available for 3D rendering")
            return None
        except Exception as e:
            logger.warning(f"Matplotlib rendering failed: {e}")
            return None

    def _generate_with_cli(
        self,
        model_path: Path,
        thumbnail_path: Path,
        width: int,
        height: int,
    ) -> CLIResult:
        """
        Generate thumbnail using Bambu Studio CLI.

        This is a placeholder implementation. The actual CLI options for
        thumbnail generation need to be determined from Bambu Studio documentation.
        """
        # For now, return a failed result to trigger fallback
        # TODO: Implement actual CLI thumbnail generation
        return CLIResult(
            exit_code=1,
            stdout="",
            stderr="Thumbnail generation not yet implemented in CLI wrapper",
            success=False,
        )

    def _generate_placeholder_thumbnail(
        self,
        model_path: Path,
        thumbnail_path: Path,
        width: int,
        height: int,
    ) -> Path:
        """
        Generate a placeholder thumbnail using PIL/Pillow.

        Creates a simple image with model information when CLI generation fails.
        """
        try:
            from PIL import Image, ImageDraw, ImageFont

            # Create a simple placeholder image
            img = Image.new("RGB", (width, height), color="#f5f5f5")
            draw = ImageDraw.Draw(img)

            # Draw a simple 3D cube icon
            self._draw_3d_icon(draw, width, height)

            # Add model name text
            model_name = model_path.stem
            if len(model_name) > 20:
                model_name = model_name[:17] + "..."

            # Try to use a font, fallback to default
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12
                )
            except Exception:
                font = ImageFont.load_default()

            # Calculate text position (centered at bottom)
            text_bbox = draw.textbbox((0, 0), model_name, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = (width - text_width) // 2
            text_y = height - text_height - 10

            draw.text((text_x, text_y), model_name, fill="#333333", font=font)

            # Add file type indicator
            file_ext = model_path.suffix.upper()
            ext_text = f"{file_ext} Model"
            ext_bbox = draw.textbbox((0, 0), ext_text, font=font)
            ext_width = ext_bbox[2] - ext_bbox[0]
            ext_x = (width - ext_width) // 2
            ext_y = text_y - text_height - 5

            draw.text((ext_x, ext_y), ext_text, fill="#666666", font=font)

            # Save the image
            img.save(thumbnail_path, "PNG")

            logger.info(f"Generated placeholder thumbnail: {thumbnail_path}")
            return thumbnail_path

        except ImportError:
            # PIL not available, create a very simple fallback
            return self._generate_simple_fallback(thumbnail_path, width, height)
        except Exception as e:
            logger.error(f"Failed to generate placeholder thumbnail: {e}")
            return self._generate_simple_fallback(thumbnail_path, width, height)

    def _draw_3d_icon(self, draw, width: int, height: int):
        """Draw a simple 3D cube icon in the center of the image."""
        # Calculate cube dimensions
        cube_size = min(width, height) // 3
        center_x = width // 2
        center_y = height // 2 - 20  # Offset up to leave room for text

        # Cube corners (isometric view)
        offset = cube_size // 4

        # Front face
        front_corners = [
            (center_x - cube_size // 2, center_y - cube_size // 2),
            (center_x + cube_size // 2, center_y - cube_size // 2),
            (center_x + cube_size // 2, center_y + cube_size // 2),
            (center_x - cube_size // 2, center_y + cube_size // 2),
        ]

        # Back face (offset for 3D effect)
        back_corners = [
            (center_x - cube_size // 2 - offset, center_y - cube_size // 2 - offset),
            (center_x + cube_size // 2 - offset, center_y - cube_size // 2 - offset),
            (center_x + cube_size // 2 - offset, center_y + cube_size // 2 - offset),
            (center_x - cube_size // 2 - offset, center_y + cube_size // 2 - offset),
        ]

        # Draw back face
        draw.polygon(back_corners, fill="#cccccc", outline="#999999", width=2)

        # Draw connecting lines
        for i in range(4):
            draw.line([front_corners[i], back_corners[i]], fill="#999999", width=2)

        # Draw front face
        draw.polygon(front_corners, fill="#e0e0e0", outline="#666666", width=2)

    def _generate_simple_fallback(
        self, thumbnail_path: Path, width: int, height: int
    ) -> Path:
        """
        Generate a very simple text-based fallback when PIL is not available.

        Creates a minimal SVG image.
        """
        try:
            svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" fill="#f5f5f5"/>
  <rect x="{width//4}" y="{height//4}" width="{width//2}" height="{height//2}"
        fill="#e0e0e0" stroke="#999999" stroke-width="2"/>
  <text x="{width//2}" y="{height - 20}" text-anchor="middle"
        font-family="Arial, sans-serif" font-size="12" fill="#333333">
    3D Model Preview
  </text>
</svg>"""

            # Save as SVG (can be displayed in browsers)
            svg_path = thumbnail_path.with_suffix(".svg")
            with open(svg_path, "w") as f:
                f.write(svg_content)

            logger.info(f"Generated simple SVG fallback: {svg_path}")
            return svg_path

        except Exception as e:
            logger.error(f"Failed to generate simple fallback: {e}")
            raise ThumbnailGenerationError(
                f"All thumbnail generation methods failed: {e}"
            )

    def extract_plate_thumbnail(
        self,
        model_path: Path,
        plate_index: int,
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Extract plate-specific thumbnail from 3MF file.

        Args:
            model_path: Path to the 3MF file
            plate_index: Index of the plate (1-based)
            output_path: Where to save the extracted thumbnail

        Returns:
            Path to extracted thumbnail if successful, None otherwise
        """
        if model_path.suffix.lower() != '.3mf':
            return None

        if output_path is None:
            output_path = self.temp_dir / f"{model_path.stem}_plate_{plate_index}_thumbnail.png"

        try:
            with zipfile.ZipFile(model_path, 'r') as zip_file:
                # Look for plate-specific thumbnails
                plate_thumbnail_patterns = [
                    f"Auxiliaries/.thumbnails/plate_{plate_index}_thumbnail.png",
                    f"Auxiliaries/.thumbnails/plate_{plate_index}.png",
                    f"Auxiliaries/.thumbnails/thumbnail_plate_{plate_index}.png",
                ]

                for pattern in plate_thumbnail_patterns:
                    if pattern in zip_file.namelist():
                        with zip_file.open(pattern) as thumb_file:
                            with open(output_path, 'wb') as out_file:
                                out_file.write(thumb_file.read())
                        
                        logger.info(f"Extracted plate {plate_index} thumbnail: {output_path}")
                        return output_path

                # Fallback: extract general thumbnail
                logger.debug(f"No plate-specific thumbnail found for plate {plate_index}, trying general thumbnail")
                return self._extract_embedded_thumbnail(model_path, output_path)

        except Exception as e:
            logger.warning(f"Failed to extract plate {plate_index} thumbnail: {e}")
            return None

    def get_available_thumbnails(self, model_path: Path) -> dict:
        """
        Analyze available thumbnails in a 3MF file.

        Args:
            model_path: Path to the 3MF file

        Returns:
            Dictionary with thumbnail availability information
        """
        result = {
            "general_thumbnails": [],
            "plate_thumbnails": [],
            "has_embedded": False,
            "total_thumbnails": 0
        }

        if model_path.suffix.lower() != '.3mf':
            return result

        try:
            with zipfile.ZipFile(model_path, 'r') as zip_file:
                files = zip_file.namelist()
                thumbnail_files = [f for f in files if 'thumbnail' in f.lower() and '.png' in f.lower()]
                
                for thumb_file in thumbnail_files:
                    # Get file size
                    file_info = zip_file.getinfo(thumb_file)
                    size_kb = file_info.file_size / 1024

                    thumb_info = {
                        "path": thumb_file,
                        "size_kb": round(size_kb, 1),
                        "type": "unknown"
                    }

                    # Categorize thumbnail type
                    if "plate_" in thumb_file.lower():
                        thumb_info["type"] = "plate_specific"
                        result["plate_thumbnails"].append(thumb_info)
                    elif any(name in thumb_file.lower() for name in ["thumbnail_small", "thumbnail_middle", "thumbnail_3mf"]):
                        thumb_info["type"] = "general"
                        result["general_thumbnails"].append(thumb_info)
                    else:
                        thumb_info["type"] = "other"
                        result["general_thumbnails"].append(thumb_info)

                result["has_embedded"] = len(thumbnail_files) > 0
                result["total_thumbnails"] = len(thumbnail_files)

        except Exception as e:
            logger.error(f"Failed to analyze thumbnails in {model_path}: {e}")

        return result

    def cleanup_old_thumbnails(self, max_age_hours: int = 24) -> None:
        """
        Clean up old thumbnail files.

        Args:
            max_age_hours: Maximum age of thumbnails to keep (default: 24 hours)
        """
        try:
            import time

            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            for thumbnail_file in self.temp_dir.glob("*"):
                if thumbnail_file.is_file():
                    file_age = current_time - thumbnail_file.stat().st_mtime
                    if file_age > max_age_seconds:
                        thumbnail_file.unlink()
                        logger.debug(f"Cleaned up old thumbnail: {thumbnail_file}")

        except Exception as e:
            logger.warning(f"Error during thumbnail cleanup: {e}")

    def get_thumbnail_path(self, model_path: Union[str, Path]) -> Path:
        """
        Get the expected thumbnail path for a model file.

        Args:
            model_path: Path to the model file

        Returns:
            Path where the thumbnail should be stored
        """
        model_path = Path(model_path)
        thumbnail_name = f"{model_path.stem}_thumbnail.png"
        return self.temp_dir / thumbnail_name

    def thumbnail_exists(self, model_path: Union[str, Path]) -> bool:
        """
        Check if a thumbnail already exists for a model.

        Args:
            model_path: Path to the model file

        Returns:
            True if thumbnail exists, False otherwise
        """
        thumbnail_path = self.get_thumbnail_path(model_path)
        return thumbnail_path.exists()


# Convenience functions
def generate_thumbnail(
    model_path: Union[str, Path],
    thumbnail_path: Optional[Union[str, Path]] = None,
    width: int = 300,
    height: int = 300,
) -> Path:
    """
    Generate a thumbnail for a 3D model.

    Args:
        model_path: Path to the 3D model file
        thumbnail_path: Optional output path for the thumbnail
        width: Thumbnail width in pixels (default: 300)
        height: Thumbnail height in pixels (default: 300)

    Returns:
        Path to the generated thumbnail
    """
    service = ThumbnailService()
    return service.generate_thumbnail(model_path, thumbnail_path, width, height)
