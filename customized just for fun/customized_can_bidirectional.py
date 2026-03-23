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
import usb.core
from gs_usb.gs_usb import GsUsb
from gs_usb.gs_usb_frame import GsUsbFrame
from gs_usb.constants import CAN_EFF_FLAG, CAN_ERR_FLAG, CAN_RTR_FLAG

# ─── Configuration ──────────────────────────────────────────────────────────
BITRATE = 500000                 # 500 kbps for both devices
SEND_INTERVAL = 2.0             # Send every 2 seconds

# CAN IDs for each device (different so we can tell them apart)
DEVICE_0_TX_ID = 0x100          # Device 0 sends with this ID
DEVICE_1_TX_ID = 0x200          # Device 1 sends with this ID

# User-defined identity and text for each device
DEVICE_0_NAME = "Ma-Meaw"
DEVICE_1_NAME = "Mok"

DEVICE_0_TEXT = "Is it we dont have the same interest, so we dont have thing to talk to each other?"
DEVICE_1_TEXT = "I do interest in you, so can we talk?"

# Tiny custom text-over-CAN framing
# Frame layout:
#   [magic, msg_id, chunk_index, total_chunks, ...chunk_bytes]
TEXT_MAGIC = 0x7E
CHUNK_SIZE = 4
INTER_CHUNK_DELAY = 0.01

# Display aliases so logs can show names as IDs.
ID_DISPLAY_NAME = {
    DEVICE_0_TX_ID: DEVICE_0_NAME,
    DEVICE_1_TX_ID: DEVICE_1_NAME,
}

# ─── CAN Mode Constants ────────────────────────────────────────────────────
GS_CAN_MODE_NORMAL = 0
GS_USB_NONE_ECHO_ID = 0xFFFFFFFF

# ─── Thread-safe print lock ────────────────────────────────────────────────
print_lock = threading.Lock()

# ─── Stop event for clean shutdown ──────────────────────────────────────────
stop_event = threading.Event()

# Reassembly state: (can_id, msg_id) -> {"total": int, "chunks": {index: bytes}}
rx_reassembly = {}
rx_lock = threading.Lock()


def safe_print(msg):
    """Thread-safe printing to avoid garbled output."""
    with print_lock:
        print(msg)


def build_text_chunks(name, text):
    """Encode '<name>|<text>' and split into protocol chunks."""
    payload = f"{name}|{text}".encode("utf-8")
    chunks = [payload[i:i + CHUNK_SIZE] for i in range(0, len(payload), CHUNK_SIZE)]
    return chunks


def decode_text_payload(raw_payload):
    """Decode UTF-8 payload into (name, text)."""
    decoded = raw_payload.decode("utf-8", errors="replace")
    if "|" in decoded:
        name, text = decoded.split("|", 1)
        return name, text
    return "Unknown", decoded


def id_display(can_id):
    """Return friendly ID display with name when known."""
    name = ID_DISPLAY_NAME.get(can_id)
    if name:
        return f"{name} (0x{can_id:03X})"
    return f"0x{can_id:03X}"


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
                data_bytes = bytes(iframe.data[:8])
                data_hex = ' '.join(f'{b:02X}' for b in data_bytes)

                # Decode our custom text protocol when possible.
                if len(data_bytes) >= 4 and data_bytes[0] == TEXT_MAGIC:
                    msg_id = data_bytes[1]
                    chunk_index = data_bytes[2]
                    total_chunks = data_bytes[3]
                    chunk_payload = data_bytes[4:]

                    if total_chunks == 0 or chunk_index >= total_chunks:
                        continue

                    with rx_lock:
                        key = (can_id, msg_id)
                        if key not in rx_reassembly:
                            rx_reassembly[key] = {"total": total_chunks, "chunks": {}}

                        entry = rx_reassembly[key]
                        entry["chunks"][chunk_index] = chunk_payload

                        if len(entry["chunks"]) == entry["total"]:
                            assembled = b"".join(
                                entry["chunks"].get(i, b"") for i in range(entry["total"])
                            )
                            del rx_reassembly[key]

                            sender_name, sender_text = decode_text_payload(assembled)
                            safe_print(
                                f"  💬 [{device_name}] RX TEXT | "
                                f"{clock_time} | "
                                f"{elapsed:>8.3f}s | "
                                f"ID={id_display(can_id)} | "
                                f"From={sender_name} | "
                                f"Text=\"{sender_text}\""
                            )
                    continue

                safe_print(
                    f"  📥 [{device_name}] RX RAW | "
                    f"{clock_time} | "
                    f"{elapsed:>8.3f}s | "
                    f"ID={id_display(can_id)} | "
                    f"Data=[{data_hex}]"
                )


def sender_thread(dev, device_name, tx_can_id, name, text, start_time):
    """
    Periodically sends CAN frames from the given device.
    """
    safe_print(f"  📤 [{device_name}] Sender thread started (TX ID=0x{tx_can_id:03X}, Name={name})")

    msg_id = 0
    while not stop_event.is_set():
        chunks = build_text_chunks(name, text)
        total_chunks = len(chunks)
        current_msg_id = msg_id

        for chunk_index, chunk in enumerate(chunks):
            data = bytes([TEXT_MAGIC, current_msg_id, chunk_index, total_chunks]) + chunk
            frame = GsUsbFrame(can_id=tx_can_id, data=data)
            dev.send(frame)

            if stop_event.is_set():
                return

            time.sleep(INTER_CHUNK_DELAY)

        clock_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        elapsed = time.time() - start_time
        safe_print(
            f"  📤 [{device_name}] TX TEXT | "
            f"{clock_time} | "
            f"{elapsed:>8.3f}s | "
            f"ID={id_display(tx_can_id)} | "
            f"From={name} | "
            f"Text=\"{text}\""
        )

        msg_id = (msg_id + 1) & 0xFF

        # Wait before next send, but check stop_event periodically
        for _ in range(int(SEND_INTERVAL * 10)):
            if stop_event.is_set():
                return
            time.sleep(0.1)


def configure_device(dev, index):
    """Stop, set bitrate, and start one device with useful error reporting."""
    try:
        try:
            dev.stop()
        except Exception:
            pass

        if not dev.set_bitrate(BITRATE):
            print(f"❌ Failed to set bitrate on Device [{index}]")
            return False

        dev.start(GS_CAN_MODE_NORMAL)
        print(f"✅ Device [{index}] configured: {BITRATE} bps, NORMAL mode")
        return True
    except usb.core.USBError as err:
        print(f"❌ Device [{index}] open/configure failed: {err}")
        print("   Likely causes:")
        print("   1) Another script is already using this device")
        print("   2) Device driver is not WinUSB (Zadig needed)")
        print("   3) Terminal needs Administrator privileges")
        print("   Fix:")
        print("   - Stop other CAN scripts (especially can_reciever.py / can_sender.py)")
        print("   - Replug the USB2CAN device")
        print("   - Run this terminal as Administrator")
        return False


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
        if not configure_device(dev, i):
            return

    print("")
    print("🚀 Starting bidirectional communication...")
    print(f"   Device [0] sends ID={id_display(DEVICE_0_TX_ID)} From={DEVICE_0_NAME}")
    print(f"   Text: \"{DEVICE_0_TEXT}\"")
    print(f"   Device [1] sends ID={id_display(DEVICE_1_TX_ID)} From={DEVICE_1_NAME}")
    print(f"   Text: \"{DEVICE_1_TEXT}\"")
    print("   Press Ctrl+C to stop")
    print("─" * 85)

    start_time = time.time()

    # ── Create 4 threads: 2 senders + 2 receivers ──────────────────────────
    threads = [
        threading.Thread(target=receiver_thread, args=(dev0, "Dev0", start_time), daemon=True),
        threading.Thread(target=receiver_thread, args=(dev1, "Dev1", start_time), daemon=True),
        threading.Thread(
            target=sender_thread,
            args=(dev0, "Dev0", DEVICE_0_TX_ID, DEVICE_0_NAME, DEVICE_0_TEXT, start_time),
            daemon=True,
        ),
        threading.Thread(
            target=sender_thread,
            args=(dev1, "Dev1", DEVICE_1_TX_ID, DEVICE_1_NAME, DEVICE_1_TEXT, start_time),
            daemon=True,
        ),
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