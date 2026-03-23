"""
=============================================================================
CAN Bus Sender Script — Innomaker USB2CAN Module
=============================================================================
This script sends CAN frames from Device [0] at 500 kbps.

Hardware: Innomaker USB2CAN-Module
Protocol: gs_usb (NOT SLCAN)
Baud Rate: 500 kbps

Prerequisites:
  pip install gs-usb==0.3.0
  Zadig WinUSB driver installed on the device

Usage:
  python can_sender.py
  Press Ctrl+C to stop
=============================================================================
"""

import time
from gs_usb.gs_usb import GsUsb
from gs_usb.gs_usb_frame import GsUsbFrame
from gs_usb.constants import CAN_EFF_FLAG, CAN_ERR_FLAG, CAN_RTR_FLAG

# ─── Configuration ──────────────────────────────────────────────────────────
DEVICE_INDEX = 0          # First USB2CAN device (sender)
BITRATE = 500000          # 500 kbps — MUST match receiver
CAN_ID = 0x123            # 11-bit standard CAN ID
SEND_INTERVAL = 1.0       # Send one frame every 1 second

# ─── CAN Mode Constants (gs_usb 0.3.0+) ────────────────────────────────────
GS_CAN_MODE_NORMAL = 0
GS_CAN_MODE_LISTEN_ONLY = (1 << 0)
GS_CAN_MODE_LOOP_BACK = (1 << 1)


def main():
    # ── Step 1: Scan for devices ────────────────────────────────────────────
    print("🔍 Scanning for USB2CAN devices...")
    devices = GsUsb.scan()

    if len(devices) == 0:
        print("❌ No USB2CAN device found! Check Zadig driver.")
        return

    if DEVICE_INDEX >= len(devices):
        print(f"❌ Device index [{DEVICE_INDEX}] not available. Found {len(devices)} device(s).")
        return

    dev = devices[DEVICE_INDEX]
    print(f"✅ Using Device [{DEVICE_INDEX}]: {dev}")

    # ── Step 2: Configure bitrate ───────────────────────────────────────────
    # IMPORTANT: Stop device first in case it was left running from a previous session
    # (If bitrate setting fails, this is usually why)
    try:
        dev.stop()
    except Exception:
        pass  # Ignore if device wasn't running

    if not dev.set_bitrate(BITRATE):
        print(f"❌ Failed to set bitrate to {BITRATE}. Try unplugging and replugging the device.")
        return
    print(f"✅ Bitrate set to {BITRATE} bps (500 kbps)")

    # ── Step 3: Start device in NORMAL mode ─────────────────────────────────
    # Use NORMAL mode because we have 2 physically connected devices
    # (Use LOOP_BACK only if testing with a single device)
    dev.start(GS_CAN_MODE_NORMAL)
    print("✅ Device started in NORMAL mode")
    print("")

    # ── Step 4: Send CAN frames ─────────────────────────────────────────────
    print(f"📤 Sending CAN frames (ID=0x{CAN_ID:03X}) every {SEND_INTERVAL}s...")
    print("   Press Ctrl+C to stop")
    print("─" * 60)

    frame_count = 0

    while True:
        # Create a test data payload — incrementing counter for easy verification
        frame_count += 1

        # Build 8 bytes of data: [counter_high, counter_low, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF]
        data = bytes([
            (frame_count >> 8) & 0xFF,  # Counter high byte
            frame_count & 0xFF,          # Counter low byte
            0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF
        ])

        # Create CAN frame
        frame = GsUsbFrame(can_id=CAN_ID, data=data)

        # Send it!
        if dev.send(frame):
            data_hex = ' '.join(f'{b:02X}' for b in data)
            print(f"  TX #{frame_count:04d} | ID: 0x{CAN_ID:03X} | DLC: {len(data)} | Data: [{data_hex}]")
        else:
            print(f"  ❌ TX #{frame_count:04d} FAILED")

        # Wait before sending next frame
        time.sleep(SEND_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Sender stopped by user.")