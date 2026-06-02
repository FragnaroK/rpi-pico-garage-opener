#!/usr/bin/env python3
"""
Quick Configuration Setup for Pico W Garage Opener (moved to tools/dev)

Call `main()` from REPL or run this module to configure the device.
"""

import json


def main():
    print("\n" + "="*60)
    print("PICO W GARAGE OPENER - CONFIGURATION SETUP")
    print("="*60)
    
    # Collect configuration
    print("\nEnter your settings (or press Enter to use defaults):\n")
    
    ssid = input("WiFi SSID []: ").strip() or ""
    password = input("WiFi Password []: ").strip() or ""
    mqtt_server = input("MQTT Server IP [192.168.1.100]: ").strip() or "192.168.1.100"
    mqtt_user = input("MQTT Username []: ").strip() or ""
    mqtt_pass = input("MQTT Password []: ").strip() or ""
    gh_user = input("GitHub Username []: ").strip() or ""
    gh_repo = input("GitHub Repository []: ").strip() or ""
    gh_branch = input("GitHub Branch [main]: ").strip() or "main"
    
    # Build config
    config = {
        'WIFI_SSID': ssid,
        'WIFI_PASSWORD': password,
        'MQTT_SERVER': mqtt_server,
        'MQTT_USER': mqtt_user,
        'MQTT_PASSWORD': mqtt_pass,
        'GH_USER': gh_user,
        'GH_REPO': gh_repo,
        'GH_BRANCH': gh_branch,
    }
    
    # Show what will be saved
    print("\n" + "="*60)
    print("CONFIGURATION TO SAVE:")
    print("="*60)
    for key, value in config.items():
        if 'PASSWORD' in key:
            print(f"  {key}: {'*' * len(value) if value else '(empty)'}")
        else:
            print(f"  {key}: {value or '(empty)'}")
    
    confirm = input("\nSave to /config.json? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return False
    
    # Save config
    try:
        with open('/config.json', 'w') as f:
            json.dump(config, f)
        print("\n✓ Configuration saved to /config.json")
        
        # Verify it was saved
        with open('/config.json', 'r') as f:
            saved = json.load(f)
        print("✓ Configuration verified")
        
        print("\n" + "="*60)
        print("NEXT STEPS:")
        print("="*60)
        print("1. Reset the Pico W (Ctrl+D in REPL or power cycle)")
        print("2. Watch for LED patterns:")
        print("   - Boot pattern: 2 quick pulses")
        print("   - WiFi pattern: Steady blink while connecting")
        print("   - Connected: 2 short pulses then LED off")
        print("3. Check error_log.txt if LED doesn't appear")
        print("")
        return True
        
    except Exception as e:
        print(f"\n✗ Failed to save config: {e}")
        return False


if __name__ == '__main__':
    main()
