#!/usr/bin/env python3
"""
LED Diagnostic Test Script (moved to tools/dev)

Call `main()` from REPL or run this module to execute diagnostics.
"""

import time
from lib.led import led
from runtime.led_scheduler import led_scheduler


def main():
    print("\n" + "="*50)
    print("LED DIAGNOSTIC TEST")
    print("="*50)

    # Test 1: Direct LED control
    print("\n[TEST 1] Direct LED control")
    print("  - Turning LED ON...")
    try:
        led.on()
        time.sleep(1)
        print("    ✓ LED ON successful")
    except Exception as e:
        print(f"    ✗ LED ON failed: {e}")

    print("  - Turning LED OFF...")
    try:
        led.off()
        time.sleep(1)
        print("    ✓ LED OFF successful")
    except Exception as e:
        print(f"    ✗ LED OFF failed: {e}")

    # Test 2: Direct blink pattern
    print("\n[TEST 2] Direct blocking blink pattern")
    print("  - Running 3x blinks (1s on/off, 2 cycles)...")
    try:
        led.blink(on_time=1, off_time=1, n=2)
        print("    ✓ Blink pattern completed")
    except Exception as e:
        print(f"    ✗ Blink pattern failed: {e}")

    # Test 3: LED Scheduler - Boot pattern
    print("\n[TEST 3] LED Scheduler - Boot pattern")
    print("  - Starting boot pattern (2 seconds, 0.5s on/off)...")
    try:
        led_scheduler.start_pattern("boot")
        print("    Pattern started, running for 2.5 seconds...")
        for i in range(25):  # 0.1s x 25 = 2.5s
            led_scheduler.update()
            time.sleep(0.1)
        print("    ✓ Boot pattern test completed")
    except Exception as e:
        print(f"    ✗ Boot pattern failed: {e}")

    # Test 4: LED Scheduler - Error pattern
    print("\n[TEST 4] LED Scheduler - Error pattern")
    print("  - Starting error pattern (1s on/off indefinitely, running for 3 seconds)...")
    try:
        led_scheduler.start_pattern("error")
        print("    Pattern started, running for 3 seconds...")
        for i in range(30):  # 0.1s x 30 = 3s
            led_scheduler.update()
            time.sleep(0.1)
        led_scheduler.stop_pattern()
        print("    ✓ Error pattern test completed")
    except Exception as e:
        print(f"    ✗ Error pattern failed: {e}")

    # Test 5: Configuration check
    print("\n[TEST 5] Configuration check")
    try:
        import runtime.config as config
        print(f"  - WIFI_SSID: {'✓ set' if config.WIFI_SSID else '✗ EMPTY - Set .env or /config.json'}")
        print(f"  - WIFI_PASSWORD: {'✓ set' if config.WIFI_PASSWORD else '✗ EMPTY'}")
        print(f"  - MQTT_SERVER: {'✓ set' if config.MQTT_SERVER else '✗ EMPTY'}")
    except Exception as e:
        print(f"  ✗ Config load failed: {e}")

    print("\n" + "="*50)
    print("DIAGNOSTIC COMPLETE")
    print("="*50)
    print("\nIf LED is not turning on during tests:")
    print("  1. Check GPIO 25 physical connection")
    print("  2. Try direct LED test via REPL: led.on(); led.off()")
    print("  3. Check if /config.json or .env exists")
    print("  4. Verify WiFi credentials in config")
    print("\n")


if __name__ == '__main__':
    main()
