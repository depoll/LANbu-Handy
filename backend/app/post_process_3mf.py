"""
Post-processing utilities for 3MF files.

This module provides functions to fix metadata in 3MF files that the
Bambu Studio CLI doesn't properly set.
"""

import logging
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def add_printer_model_id_to_3mf(
    input_path: Path, printer_model_id: str, output_path: Optional[Path] = None
) -> Path:
    """
    Add printer_model_id to a 3MF file's slice_info.config.

    The Bambu Studio CLI doesn't properly set printer_model_id even when the
    machine_full directory is available. This function adds it in post-processing.

    Args:
        input_path: Path to the input 3MF file
        printer_model_id: The printer model ID (e.g., "BL-P001" for X1 Carbon)
        output_path: Optional output path. If None, modifies the input file in place.

    Returns:
        Path to the modified file
    """
    if output_path is None:
        output_path = input_path

    # Create a temporary file to work with
    with tempfile.NamedTemporaryFile(
        mode="wb", delete=False, suffix=".3mf"
    ) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        # Copy the original file to temp
        with open(input_path, "rb") as src, open(temp_path, "wb") as dst:
            dst.write(src.read())

        # Modify the slice_info.config in the temp file
        updated = False
        with zipfile.ZipFile(temp_path, "r") as zip_in:
            # Read all files first
            file_list = zip_in.namelist()
            file_data = {}
            for file_name in file_list:
                file_data[file_name] = zip_in.read(file_name)

        # Modify slice_info.config if it exists
        slice_info_path = "Metadata/slice_info.config"
        if slice_info_path in file_data:
            # Parse the XML
            tree = ET.fromstring(file_data[slice_info_path])

            # Find all plate elements and update printer_model_id
            for plate in tree.findall(".//plate"):
                for metadata in plate.findall("metadata"):
                    if metadata.get("key") == "printer_model_id":
                        current_value = metadata.get("value", "")
                        if not current_value:
                            metadata.set("value", printer_model_id)
                            updated = True
                            logger.info(
                                f"Updated printer_model_id to '{printer_model_id}' "
                                f"in {input_path}"
                            )
                        else:
                            logger.info(
                                f"printer_model_id already set to '{current_value}' "
                                f"in {input_path}"
                            )

            # Convert back to string
            file_data[slice_info_path] = ET.tostring(
                tree, encoding="UTF-8", xml_declaration=True
            )

        # Write the modified data to a new zip file
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zip_out:
            for file_name, data in file_data.items():
                zip_out.writestr(file_name, data)

        if updated:
            logger.info(f"Successfully post-processed {output_path}")
        else:
            logger.warning(f"No printer_model_id field found to update in {input_path}")

        return output_path

    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()
