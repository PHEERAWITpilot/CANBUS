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
SEND_INTERVAL = 2.0       # Send one full text every 2 seconds

# Text payload configuration (alternating sender identities)
SENDER_PROFILES = [
    {
        "can_id": 0x100,
        "name": "Ma-Meaw",
        "text": "Is it we dont have the same interest, so we dont have thing to talk to each other?",
    },
    {
        "can_id": 0x200,
        "name": "Mok",
        "text": "I do interest in you, so can we talk?",
    },
]

# Tiny custom text-over-CAN framing
# Frame layout: [magic, msg_id, chunk_index, total_chunks, ...chunk_bytes]
TEXT_MAGIC = 0x7E
CHUNK_SIZE = 4
INTER_CHUNK_DELAY = 0.01

# ─── CAN Mode Constants (gs_usb 0.3.0+) ────────────────────────────────────
GS_CAN_MODE_NORMAL = 0
GS_CAN_MODE_LISTEN_ONLY = (1 << 0)
GS_CAN_MODE_LOOP_BACK = (1 << 1)


def build_text_chunks(name, text):
    """Encode '<name>|<text>' and split into protocol chunks."""
    payload = f"{name}|{text}".encode("utf-8")
    return [payload[i:i + CHUNK_SIZE] for i in range(0, len(payload), CHUNK_SIZE)]


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
    print(f"📤 Sending alternating text-over-CAN every {SEND_INTERVAL}s...")
    for profile in SENDER_PROFILES:
        print(
            f"   ID=0x{profile['can_id']:03X} | "
            f"From={profile['name']} | Text=\"{profile['text']}\""
        )
    print("   Press Ctrl+C to stop")
    print("─" * 60)

    frame_count = 0
    msg_id = 0
    profile_index = 0

    while True:
        frame_count += 1
        profile = SENDER_PROFILES[profile_index]
        can_id = profile["can_id"]
        sender_name = profile["name"]
        sender_text = profile["text"]

        chunks = build_text_chunks(sender_name, sender_text)
        total_chunks = len(chunks)
        current_msg_id = msg_id
        tx_ok = True

        for chunk_index, chunk in enumerate(chunks):
            data = bytes([TEXT_MAGIC, current_msg_id, chunk_index, total_chunks]) + chunk
            frame = GsUsbFrame(can_id=can_id, data=data)
            if not dev.send(frame):
                tx_ok = False
                break
            time.sleep(INTER_CHUNK_DELAY)

        if tx_ok:
            print(
                f"  TX #{frame_count:04d} | ID: 0x{can_id:03X} | "
                f"From={sender_name} | Text=\"{sender_text}\""
            )
        else:
            print(f"  ❌ TX #{frame_count:04d} FAILED")

        msg_id = (msg_id + 1) & 0xFF
        profile_index = (profile_index + 1) % len(SENDER_PROFILES)

        # Wait before sending next frame
        time.sleep(SEND_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Sender stopped by user.")