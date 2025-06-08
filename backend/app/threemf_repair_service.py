"""
LANbu Handy - 3MF Repair Service for Three.js Compatibility

This module provides functionality to repair Bambu Studio 3MF files for better
compatibility with Three.js ThreeMFLoader by merging external object mesh data
into the main model file.
"""

import logging
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ThreeMFRepairError(Exception):
    """Exception raised when 3MF repair operations fail."""

    pass


class ThreeMFRepairService:
    """Service to repair Bambu Studio 3MF files for Three.js compatibility."""

    def __init__(self):
        """Initialize the repair service."""
        self.default_namespace = (
            "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
        )
        self.temp_dir = Path(tempfile.gettempdir()) / "lanbu-handy" / "repaired-3mf"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_repaired_3mf_path(self, original_path: Path) -> Path:
        """
        Get the path where a repaired 3MF file would be stored.

        Args:
            original_path: Path to the original 3MF file

        Returns:
            Path where the repaired file would be stored
        """
        return self.temp_dir / f"repaired_{original_path.name}"

    def needs_repair(self, file_path: Path) -> bool:
        """
        Check if a 3MF file needs repair (has external object references).

        Args:
            file_path: Path to the 3MF file to check

        Returns:
            True if the file needs repair, False otherwise
        """
        if file_path.suffix.lower() != ".3mf":
            return False

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                # Check if there are separate object files
                object_files = [
                    f
                    for f in zf.namelist()
                    if f.startswith("3D/Objects/") and f.endswith(".model")
                ]
                return len(object_files) > 0

        except Exception as e:
            logger.warning(f"Error checking if 3MF needs repair: {e}")
            return False

    def repair_3mf_file(self, input_path: Path) -> Path:
        """
        Repair a 3MF file by merging mesh data into the main model file.

        Args:
            input_path: Path to the original 3MF file

        Returns:
            Path to the repaired 3MF file

        Raises:
            ThreeMFRepairError: If repair fails
        """
        output_path = self.get_repaired_3mf_path(input_path)

        # If repaired file already exists and is newer than original, use it
        if (
            output_path.exists()
            and output_path.stat().st_mtime > input_path.stat().st_mtime
        ):
            logger.debug(f"Using existing repaired 3MF file: {output_path}")
            return output_path

        try:
            logger.info(f"Repairing 3MF file: {input_path}")

            with zipfile.ZipFile(input_path, "r") as input_zip:
                # Read main model file
                main_model_content = self._read_main_model(input_zip)
                if not main_model_content:
                    raise ThreeMFRepairError("Failed to read main model file")

                # Extract all mesh data from object files
                mesh_data = self._extract_mesh_data(input_zip)
                if not mesh_data:
                    logger.warning("No external mesh data found, copying original file")
                    # If no external mesh data, just copy the original file
                    output_path.write_bytes(input_path.read_bytes())
                    return output_path

                # Merge mesh data into main model
                repaired_model = self._merge_mesh_data(main_model_content, mesh_data)
                if not repaired_model:
                    raise ThreeMFRepairError("Failed to merge mesh data")

                # Create repaired 3MF file
                self._create_repaired_3mf(input_zip, repaired_model, output_path)

                logger.info(f"Successfully repaired 3MF file: {output_path}")
                return output_path

        except Exception as e:
            logger.error(f"Error repairing 3MF file {input_path}: {e}")
            raise ThreeMFRepairError(f"Failed to repair 3MF file: {str(e)}")

    def _read_main_model(self, zip_file: zipfile.ZipFile) -> Optional[str]:
        """Read the main 3dmodel.model file content."""
        try:
            with zip_file.open("3D/3dmodel.model") as model_file:
                return model_file.read().decode("utf-8")
        except Exception as e:
            logger.error(f"Error reading main model file: {e}")
            return None

    def _extract_mesh_data(
        self, zip_file: zipfile.ZipFile
    ) -> Dict[str, List[ET.Element]]:
        """
        Extract mesh data from all object files.

        Returns:
            Dictionary mapping object IDs to their mesh elements
        """
        mesh_data = {}

        # Find all object model files
        object_files = [
            f
            for f in zip_file.namelist()
            if f.startswith("3D/Objects/") and f.endswith(".model")
        ]

        for obj_file in object_files:
            try:
                with zip_file.open(obj_file) as model_file:
                    content = model_file.read().decode("utf-8")
                    root = ET.fromstring(content)

                    # Extract object ID from filename (e.g., object_1.model -> 1)
                    obj_id = (
                        obj_file.split("/")[-1]
                        .replace("object_", "")
                        .replace(".model", "")
                    )

                    # Find all mesh elements
                    meshes = root.findall(f".//{{{self.default_namespace}}}mesh")
                    if meshes:
                        mesh_data[obj_id] = meshes
                        logger.debug(f"Found {len(meshes)} meshes in {obj_file}")

            except Exception as e:
                logger.warning(f"Error reading {obj_file}: {e}")
                continue

        return mesh_data

    def _merge_mesh_data(
        self, main_model_content: str, mesh_data: Dict[str, List[ET.Element]]
    ) -> Optional[str]:
        """
        Merge mesh data into the main model file.

        Args:
            main_model_content: Original main model XML content
            mesh_data: Dictionary of mesh elements by object ID

        Returns:
            Repaired model content with embedded mesh data
        """
        try:
            # Parse main model
            root = ET.fromstring(main_model_content)

            # Find all objects in main model
            objects = root.findall(f".//{{{self.default_namespace}}}object")

            for obj in objects:
                obj_id = obj.get("id")

                # Look for components that reference external objects
                components = obj.findall(f".//{{{self.default_namespace}}}component")

                for component in components:
                    component_obj_id = component.get("objectid")

                    # If we have mesh data for this component object,
                    # add it directly to the parent object
                    if component_obj_id in mesh_data:
                        meshes = mesh_data[component_obj_id]

                        # Create a mesh container if it doesn't exist
                        mesh_container = obj.find(f"{{{self.default_namespace}}}mesh")
                        if mesh_container is None:
                            mesh_container = ET.SubElement(
                                obj, f"{{{self.default_namespace}}}mesh"
                            )

                        # Add all mesh data from the component
                        for mesh in meshes:
                            # Copy vertices
                            vertices = mesh.find(
                                f"{{{self.default_namespace}}}vertices"
                            )
                            if vertices is not None:
                                existing_vertices = mesh_container.find(
                                    f"{{{self.default_namespace}}}vertices"
                                )
                                if existing_vertices is None:
                                    mesh_container.append(vertices)
                                else:
                                    # Merge vertices
                                    for vertex in vertices:
                                        existing_vertices.append(vertex)

                            # Copy triangles
                            triangles = mesh.find(
                                f"{{{self.default_namespace}}}triangles"
                            )
                            if triangles is not None:
                                existing_triangles = mesh_container.find(
                                    f"{{{self.default_namespace}}}triangles"
                                )
                                if existing_triangles is None:
                                    mesh_container.append(triangles)
                                else:
                                    # Merge triangles
                                    for triangle in triangles:
                                        existing_triangles.append(triangle)

                        logger.debug(
                            f"Merged mesh from obj {component_obj_id} into obj {obj_id}"
                        )

            # Convert back to string
            ET.register_namespace("", self.default_namespace)
            repaired_content = ET.tostring(root, encoding="unicode")

            # Fix the XML declaration and formatting
            repaired_content = (
                f'<?xml version="1.0" encoding="UTF-8"?>\n{repaired_content}'
            )

            return repaired_content

        except Exception as e:
            logger.error(f"Error merging mesh data: {e}")
            return None

    def _create_repaired_3mf(
        self,
        input_zip: zipfile.ZipFile,
        repaired_model: str,
        output_path: Path,
    ):
        """
        Create a new 3MF file with the repaired model.

        Args:
            input_zip: Original zip file
            repaired_model: Repaired model XML content
            output_path: Where to save the repaired file
        """
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as output_zip:
            # Copy essential files
            essential_files = [
                "_rels/.rels",
                "[Content_Types].xml",
                "3D/_rels/3dmodel.model.rels",
            ]

            for file_name in essential_files:
                if file_name in input_zip.namelist():
                    try:
                        with input_zip.open(file_name) as source_file:
                            output_zip.writestr(file_name, source_file.read())
                    except Exception as e:
                        logger.warning(f"Could not copy {file_name}: {e}")

            # Write the repaired main model
            output_zip.writestr("3D/3dmodel.model", repaired_model.encode("utf-8"))

            # Copy thumbnails and metadata (optional but helpful)
            for file_name in input_zip.namelist():
                if (
                    file_name.startswith("Auxiliaries/")
                    or file_name.startswith("Metadata/")
                    and any(
                        file_name.endswith(ext)
                        for ext in [".png", ".jpg", ".jpeg", ".config"]
                    )
                ):
                    try:
                        with input_zip.open(file_name) as source_file:
                            output_zip.writestr(file_name, source_file.read())
                    except Exception as e:
                        logger.debug(f"Could not copy optional file {file_name}: {e}")

    def cleanup_old_repaired_files(self, max_age_hours: int = 24):
        """
        Clean up old repaired files to save disk space.

        Args:
            max_age_hours: Maximum age of files to keep in hours
        """
        try:
            import time

            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            for file_path in self.temp_dir.glob("repaired_*.3mf"):
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    file_path.unlink()
                    logger.debug(f"Cleaned up old repaired file: {file_path}")

        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
