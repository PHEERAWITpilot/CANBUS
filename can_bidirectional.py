"""
=============================================================================
Bidirectional CAN Bus Communication — Innomaker USB2CAN Module
=============================================================================
This script uses THREADING to simultaneously:
  - Send from Device [0] → Device [1]
  - Send from Device [1] → Device [0]

Both devices send and receive at the same time, demonstrating full
bidirectional CAN bus communication.

Prerequisites:
  pip install gs-usb==0.3.0

Usage:
  python can_bidirectional.py
  Press Ctrl+C to stop
=============================================================================
"""

import time
import threading
from datetime import datetime
from gs_usb.gs_usb import GsUsb
from gs_usb.gs_usb_frame import GsUsbFrame
from gs_usb.constants import CAN_EFF_FLAG, CAN_ERR_FLAG, CAN_RTR_FLAG

# ─── Configuration ──────────────────────────────────────────────────────────
BITRATE = 500000                 # 500 kbps for both devices
SEND_INTERVAL = 2.0             # Send every 2 seconds

# CAN IDs for each device (different so we can tell them apart)
DEVICE_0_TX_ID = 0x100          # Device 0 sends with this ID
DEVICE_1_TX_ID = 0x200          # Device 1 sends with this ID

# ─── CAN Mode Constants ────────────────────────────────────────────────────
GS_CAN_MODE_NORMAL = 0
GS_USB_NONE_ECHO_ID = 0xFFFFFFFF

# ─── Thread-safe print lock ────────────────────────────────────────────────
print_lock = threading.Lock()

# ─── Stop event for clean shutdown ──────────────────────────────────────────
stop_event = threading.Event()


def safe_print(msg):
    """Thread-safe printing to avoid garbled output."""
    with print_lock:
        print(msg)


def receiver_thread(dev, device_name, start_time):
    """
    Continuously reads CAN frames from the given device.
    Filters out echo frames (frames sent by this same device).
    """
    safe_print(f"  📥 [{device_name}] Receiver thread started")

    while not stop_event.is_set():
        iframe = GsUsbFrame()
        if dev.read(iframe, 1):  # 1ms timeout
            # Only process received frames, not echoes of our own transmissions
            if iframe.echo_id == GS_USB_NONE_ECHO_ID:
                # Check for error frames
                if iframe.can_id & CAN_ERR_FLAG:
                    continue  # Skip error frames

                # Get timestamps
                clock_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                elapsed = time.time() - start_time

                # Extract actual CAN ID
                is_extended = bool(iframe.can_id & CAN_EFF_FLAG)
                can_id = iframe.can_id & (0x1FFFFFFF if is_extended else 0x7FF)

                # Format data
                data_hex = ' '.join(f'{b:02X}' for b in iframe.data[:8])

                safe_print(
                    f"  📥 [{device_name}] RX | "
                    f"{clock_time} | "
                    f"{elapsed:>8.3f}s | "
                    f"ID=0x{can_id:03X} | "
                    f"Data=[{data_hex}]"
                )


def sender_thread(dev, device_name, tx_can_id, start_time):
    """
    Periodically sends CAN frames from the given device.
    """
    safe_print(f"  📤 [{device_name}] Sender thread started (TX ID=0x{tx_can_id:03X})")

    count = 0
    while not stop_event.is_set():
        count += 1

        # Build payload: [device_marker, counter_high, counter_low, ...]
        # Device 0 uses 0xAA marker, Device 1 uses 0xBB
        marker = 0xAA if tx_can_id == DEVICE_0_TX_ID else 0xBB
        data = bytes([
            marker,
            (count >> 8) & 0xFF,
            count & 0xFF,
            0x11, 0x22, 0x33, 0x44, 0x55
        ])

        frame = GsUsbFrame(can_id=tx_can_id, data=data)

        if dev.send(frame):
            clock_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            elapsed = time.time() - start_time
            data_hex = ' '.join(f'{b:02X}' for b in data)
            safe_print(
                f"  📤 [{device_name}] TX | "
                f"{clock_time} | "
                f"{elapsed:>8.3f}s | "
                f"ID=0x{tx_can_id:03X} | "
                f"Data=[{data_hex}]"
            )

        # Wait before next send, but check stop_event periodically
        for _ in range(int(SEND_INTERVAL * 10)):
            if stop_event.is_set():
                return
            time.sleep(0.1)


def main():
    print("=" * 75)
    print("  Bidirectional CAN Bus Communication Test")
    print("  Innomaker USB2CAN Module × 2")
    print("=" * 75)
    print("")

    # ── Scan for devices ────────────────────────────────────────────────────
    print("🔍 Scanning for USB2CAN devices...")
    devices = GsUsb.scan()

    if len(devices) < 2:
        print(f"❌ Need 2 USB2CAN devices, found {len(devices)}")
        return

    dev0 = devices[0]
    dev1 = devices[1]
    print(f"✅ Device [0]: {dev0}")
    print(f"✅ Device [1]: {dev1}")
    print("")

    # ── Configure both devices ──────────────────────────────────────────────
    for i, dev in enumerate([dev0, dev1]):
        try:
            dev.stop()
        except Exception:
            pass

        if not dev.set_bitrate(BITRATE):
            print(f"❌ Failed to set bitrate on Device [{i}]")
            return

        dev.start(GS_CAN_MODE_NORMAL)
        print(f"✅ Device [{i}] configured: {BITRATE} bps, NORMAL mode")

    print("")
    print("🚀 Starting bidirectional communication...")
    print("   Device [0] sends ID=0x100 (marker 0xAA)")
    print("   Device [1] sends ID=0x200 (marker 0xBB)")
    print("   Press Ctrl+C to stop")
    print("─" * 85)

    start_time = time.time()

    # ── Create 4 threads: 2 senders + 2 receivers ──────────────────────────
    threads = [
        threading.Thread(target=receiver_thread, args=(dev0, "Dev0", start_time), daemon=True),
        threading.Thread(target=receiver_thread, args=(dev1, "Dev1", start_time), daemon=True),
        threading.Thread(target=sender_thread, args=(dev0, "Dev0", DEVICE_0_TX_ID, start_time), daemon=True),
        threading.Thread(target=sender_thread, args=(dev1, "Dev1", DEVICE_1_TX_ID, start_time), daemon=True),
    ]

    # Start all threads
    for t in threads:
        t.start()

    # Wait for Ctrl+C
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n\n🛑 Stopping all threads...")
        stop_event.set()
        for t in threads:
            t.join(timeout=3)
        print("✅ All threads stopped. Done!")


if __name__ == "__main__":
    main()