#!/usr/bin/env python3
"""
Test script to validate virtual display functionality for Bambu Studio CLI.

This script tests PNG thumbnail generation using the CLI with virtual display support.
"""

import tempfile
from pathlib import Path
import sys
import os

# Add the backend path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.slicer_service import BambuStudioCLIWrapper, export_png
from app.thumbnail_service import ThumbnailService


def test_cli_png_export():
    """Test CLI PNG export functionality."""
    print("Testing CLI PNG export functionality...")
    
    # Test file path
    test_file = Path(__file__).parent / "test_files" / "Original3DBenchy3Dprintconceptsnormel.3mf"
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return False
    
    # Create temporary output directory
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        print(f"📁 Test file: {test_file}")
        print(f"📁 Output directory: {output_dir}")
        
        # Test CLI wrapper directly
        wrapper = BambuStudioCLIWrapper()
        result = wrapper.export_png(test_file, output_dir, plate_number=0)
        
        print(f"🔧 CLI command exit code: {result.exit_code}")
        print(f"📝 CLI stdout: {result.stdout}")
        print(f"⚠️  CLI stderr: {result.stderr}")
        
        if result.success:
            # Check for generated PNG files
            png_files = list(output_dir.glob("*.png"))
            print(f"🖼️  Generated PNG files: {len(png_files)}")
            
            for png_file in png_files:
                print(f"   - {png_file.name} ({png_file.stat().st_size} bytes)")
            
            return len(png_files) > 0
        else:
            print("❌ CLI PNG export failed")
            return False


def test_thumbnail_service():
    """Test the thumbnail service with CLI backend."""
    print("\nTesting ThumbnailService with CLI backend...")
    
    # Test file path
    test_file = Path(__file__).parent / "test_files" / "multicolor-test-coin.3mf"
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return False
    
    service = ThumbnailService()
    
    try:
        thumbnail_path = service.generate_thumbnail(test_file, width=300, height=300)
        print(f"🖼️  Generated thumbnail: {thumbnail_path}")
        
        if thumbnail_path.exists():
            print(f"✅ Thumbnail file created: {thumbnail_path.stat().st_size} bytes")
            return True
        else:
            print("❌ Thumbnail file not found")
            return False
            
    except Exception as e:
        print(f"❌ Thumbnail generation failed: {e}")
        return False


def test_virtual_display_availability():
    """Test if virtual display wrapper is available."""
    print("Testing virtual display wrapper availability...")
    
    wrapper = BambuStudioCLIWrapper()
    has_display_wrapper = wrapper.use_display_wrapper
    
    print(f"🖥️  Virtual display wrapper available: {has_display_wrapper}")
    
    # Test help command (should work with or without display)
    help_result = wrapper.get_help()
    print(f"📖 CLI help command success: {help_result.success}")
    
    return help_result.success


def main():
    """Run all tests."""
    print("🧪 Testing Bambu Studio CLI Virtual Display Functionality")
    print("=" * 60)
    
    tests = [
        ("Virtual Display Availability", test_virtual_display_availability),
        ("CLI PNG Export", test_cli_png_export),
        ("Thumbnail Service", test_thumbnail_service),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}")
        print("-" * 40)
        
        try:
            success = test_func()
            results.append((test_name, success))
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"Result: {status}")
            
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("🏁 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())