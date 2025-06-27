#!/usr/bin/env python3
"""Test script to verify printer switching doesn't hang."""

import asyncio
import time

import aiohttp


async def test_printer_switch():
    """Test switching between printers to ensure no hanging."""
    base_url = "http://localhost:8000"

    # Test printer configurations
    printers = [
        {
            "ip": "192.168.1.100",
            "name": "Test Printer 1",
            "access_code": "12345678",
            "serial_number": "01S00A1234567890",
        },
        {
            "ip": "192.168.1.101",
            "name": "Test Printer 2",
            "access_code": "87654321",
            "serial_number": "01S00A0987654321",
        },
    ]

    async with aiohttp.ClientSession() as session:
        for i in range(5):  # Test 5 switches
            printer = printers[i % 2]
            print(f"\nAttempt {i+1}: Switching to {printer['name']} ({printer['ip']})")

            start_time = time.time()
            try:
                async with session.post(
                    f"{base_url}/api/printer/set-active",
                    json=printer,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    elapsed = time.time() - start_time
                    result = await response.json()

                    if response.status == 200:
                        print(
                            f"✓ Success in {elapsed:.2f}s: "
                            f"{result.get('message', 'OK')}"
                        )
                    else:
                        print(f"✗ Failed with status {response.status}: {result}")

            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                print(f"✗ Timeout after {elapsed:.2f}s")
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"✗ Error after {elapsed:.2f}s: {e}")

            # Short delay between switches
            await asyncio.sleep(1)

    print("\n✅ Test completed")


if __name__ == "__main__":
    print("Testing printer switching...")
    print("Make sure the dev servers are running!")
    asyncio.run(test_printer_switch())
