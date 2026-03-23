"""
=============================================================================
CAN Bus Receiver Script — Innomaker USB2CAN Module (with Timestamps)
=============================================================================
Usage:
  1. Run this script FIRST: python can_receiver.py
  2. Then run can_sender.py in another terminal
  Press Ctrl+C to stop
=============================================================================
"""

import time
from datetime import datetime
from gs_usb.gs_usb import GsUsb
from gs_usb.gs_usb_frame import GsUsbFrame
from gs_usb.constants import CAN_EFF_FLAG, CAN_ERR_FLAG, CAN_RTR_FLAG

# ─── Configuration ──────────────────────────────────────────────────────────
DEVICE_INDEX = 1          # Second USB2CAN device (receiver)
BITRATE = 500000          # 500 kbps — MUST match sender
READ_TIMEOUT_MS = 1       # Timeout per read attempt (ms)

# Optional ID-to-name display aliases
ID_NAME_MAP = {
    0x100: "Ma-Meaw",
    0x200: "Mok",
}

# ─── CAN Mode Constants ────────────────────────────────────────────────────
GS_CAN_MODE_NORMAL = 0
GS_USB_NONE_ECHO_ID = 0xFFFFFFFF

# Tiny custom text-over-CAN framing
TEXT_MAGIC = 0x7E

# Reassembly state: (can_id, msg_id) -> {"total": int, "chunks": {index: bytes}}
RX_REASSEMBLY = {}


def decode_can_id(raw_can_id):
    """Decode the raw CAN ID and extract flags."""
    is_extended = bool(raw_can_id & CAN_EFF_FLAG)
    is_rtr = bool(raw_can_id & CAN_RTR_FLAG)
    is_error = bool(raw_can_id & CAN_ERR_FLAG)

    if is_extended:
        can_id = raw_can_id & 0x1FFFFFFF
    else:
        can_id = raw_can_id & 0x7FF

    return can_id, is_extended, is_rtr, is_error


def decode_text_payload(raw_payload):
    """Decode UTF-8 payload in format '<name>|<text>'."""
    decoded = raw_payload.decode("utf-8", errors="replace")
    if "|" in decoded:
        name, text = decoded.split("|", 1)
        return name, text
    return "Unknown", decoded


def main():
    print("🔍 Scanning for USB2CAN devices...")
    devices = GsUsb.scan()

    if len(devices) == 0:
        print("❌ No USB2CAN device found!")
        return

    if DEVICE_INDEX >= len(devices):
        print(f"❌ Device index [{DEVICE_INDEX}] not available.")
        return

    dev = devices[DEVICE_INDEX]
    print(f"✅ Using Device [{DEVICE_INDEX}]: {dev}")

    try:
        dev.stop()
    except Exception:
        pass

    if not dev.set_bitrate(BITRATE):
        print(f"❌ Failed to set bitrate to {BITRATE}.")
        return
    print(f"✅ Bitrate set to {BITRATE} bps (500 kbps)")

    dev.start(GS_CAN_MODE_NORMAL)
    print("✅ Device started in NORMAL mode")
    print("")

    print("📥 Listening for CAN frames...")
    print("   Press Ctrl+C to stop")
    print("─" * 85)
    print(f"  {'#':>5} | {'Clock Time':>14} | {'Elapsed':>9} | {'ID':>10} | {'DLC':>3} | {'Data':<24} | Flags")
    print("─" * 85)

    rx_count = 0
    start_time = time.time()

    while True:
        iframe = GsUsbFrame()

        if dev.read(iframe, READ_TIMEOUT_MS):
            if iframe.echo_id == GS_USB_NONE_ECHO_ID:
                rx_count += 1

                # ── Two types of timestamp ──────────────────────────────
                # 1. Clock time — real wall clock (useful for correlation)
                clock_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                # 2. Elapsed time — seconds since receiver started
                elapsed = time.time() - start_time

                # ── Decode CAN ID and flags ─────────────────────────────
                can_id, is_extended, is_rtr, is_error = decode_can_id(iframe.can_id)

                if is_error:
                    print(f"  {'ERR':>5} | {clock_time:>14} | {elapsed:>8.3f}s | ERROR FRAME")
                    continue

                data_bytes = iframe.data[:iframe.can_dlc] if hasattr(iframe, 'can_dlc') else iframe.data
                data_hex = ' '.join(f'{b:02X}' for b in data_bytes)

                if is_extended:
                    id_str = f"0x{can_id:08X}"
                else:
                    id_str = f"0x{can_id:03X}"

                id_name = ID_NAME_MAP.get(can_id)
                if id_name:
                    id_str = f"{id_name}({id_str})"

                flags = []
                if is_extended:
                    flags.append("EXT")
                if is_rtr:
                    flags.append("RTR")
                flags_str = ','.join(flags) if flags else "STD"

                dlc = len(data_bytes)

                # Decode our custom text protocol when possible.
                if dlc >= 4 and data_bytes[0] == TEXT_MAGIC:
                    msg_id = data_bytes[1]
                    chunk_index = data_bytes[2]
                    total_chunks = data_bytes[3]
                    chunk_payload = bytes(data_bytes[4:])

                    if total_chunks == 0 or chunk_index >= total_chunks:
                        continue

                    key = (can_id, msg_id)
                    if key not in RX_REASSEMBLY:
                        RX_REASSEMBLY[key] = {"total": total_chunks, "chunks": {}}

                    entry = RX_REASSEMBLY[key]
                    entry["chunks"][chunk_index] = chunk_payload

                    if len(entry["chunks"]) == entry["total"]:
                        assembled = b"".join(
                            entry["chunks"].get(i, b"") for i in range(entry["total"])
                        )
                        del RX_REASSEMBLY[key]

                        sender_name, sender_text = decode_text_payload(assembled)
                        print(
                            f"  💬 TEXT | {clock_time:>14} | {elapsed:>8.3f}s | "
                            f"ID: {id_str} | From: {sender_name} | Text: \"{sender_text}\""
                        )
                    continue

                print(
                    f"  {rx_count:>5} | "
                    f"{clock_time:>14} | "
                    f"{elapsed:>8.3f}s | "
                    f"{id_str:>10} | "
                    f"{dlc:>3} | "
                    f"{data_hex:<24} | "
                    f"{flags_str}"
                )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n🛑 Receiver stopped by user.")