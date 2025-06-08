#!/usr/bin/env python3
"""
Verification script to test if model preview is using repaired 3MF files.
"""

import shutil
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

# Import the FastAPI app and services
from backend.app.main import app, model_service, threemf_repair_service


def test_repair_verification():
    """Test to verify that model preview is serving the repaired 3MF file."""
    client = TestClient(app)
    
    # Use a test 3MF file that needs repair
    test_files_dir = Path(__file__).parent / "test_files"
    test_file = test_files_dir / "Original3DBenchy3Dprintconceptsnormel.3mf"
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return
    
    print(f"✅ Found test file: {test_file}")
    
    # Create temporary directory for model service
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Temporarily set model service temp dir
        original_temp_dir = model_service.temp_dir
        model_service.temp_dir = temp_path
        
        try:
            # Copy test file to temp directory
            test_file_copy = temp_path / test_file.name
            shutil.copy2(test_file, test_file_copy)
            print(f"✅ Copied test file to: {test_file_copy}")
            
            # Check if the file needs repair
            needs_repair = threemf_repair_service.needs_repair(test_file_copy)
            print(f"📋 File needs repair: {needs_repair}")
            
            if needs_repair:
                # Manually repair the file to get the repaired version
                repaired_file_path = threemf_repair_service.repair_3mf_file(test_file_copy)
                print(f"🔧 Repaired file created at: {repaired_file_path}")
                print(f"📏 Original file size: {test_file_copy.stat().st_size} bytes")
                print(f"📏 Repaired file size: {repaired_file_path.stat().st_size} bytes")
                
                # Read content of repaired file for comparison
                repaired_content = repaired_file_path.read_bytes()
                original_content = test_file_copy.read_bytes()
                
                print(f"🔍 Original and repaired files are {'identical' if repaired_content == original_content else 'different'}")
                
                # Now test the preview endpoint
                response = client.get(f"/api/model/preview/{test_file.name}")
                print(f"🌐 Preview endpoint response status: {response.status_code}")
                
                if response.status_code == 200:
                    response_content = response.content
                    print(f"📏 Preview response size: {len(response_content)} bytes")
                    
                    # Check which file the response matches
                    if response_content == repaired_content:
                        print("✅ SUCCESS: Preview endpoint is serving the REPAIRED file")
                    elif response_content == original_content:
                        print("❌ ISSUE FOUND: Preview endpoint is serving the ORIGINAL file (not repaired)")
                    else:
                        print("⚠️  UNKNOWN: Preview endpoint is serving different content than both original and repaired files")
                        print(f"   Response hash: {hash(response_content)}")
                        print(f"   Original hash: {hash(original_content)}")
                        print(f"   Repaired hash: {hash(repaired_content)}")
                else:
                    print(f"❌ Preview endpoint failed with status: {response.status_code}")
                    print(f"   Response: {response.json()}")
            else:
                print("ℹ️  File does not need repair, cannot test repair functionality")
                
        finally:
            # Restore original temp dir
            model_service.temp_dir = original_temp_dir


if __name__ == "__main__":
    test_repair_verification()