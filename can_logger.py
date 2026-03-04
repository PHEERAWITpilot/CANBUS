"""
=============================================================================
CAN Bus Logger & Analyzer — Innomaker USB2CAN Module
=============================================================================
Features:
  - Logs ALL received CAN frames to CSV and ASC files simultaneously
  - Filters messages by CAN ID (optional)
  - Displays real-time statistics on exit
  - ASC format is compatible with Vector CANalyzer / SavvyCAN

Log files are saved to the "can_logs" folder with timestamps in filenames.

Prerequisites:
  pip install gs-usb==0.3.0

Usage:
  python can_logger.py
  Press Ctrl+C to stop and save
=============================================================================
"""

import time
import csv
import os
from datetime import datetime
from gs_usb.gs_usb import GsUsb
from gs_usb.gs_usb_frame import GsUsbFrame
from gs_usb.constants import CAN_EFF_FLAG, CAN_ERR_FLAG, CAN_RTR_FLAG

# ─── Configuration ──────────────────────────────────────────────────────────
DEVICE_INDEX = 1            # Which device to log from (1 = receiver)
BITRATE = 500000            # 500 kbps

# Logging options
LOG_TO_CSV = True           # Save to CSV file
LOG_TO_ASC = True           # Save to ASC file (Vector CANalyzer compatible)
LOG_DIR = "can_logs"        # Directory for log files

# Filter options (set to None to capture ALL CAN IDs)
FILTER_CAN_IDS = None       # Log everything
# FILTER_CAN_IDS = [0x123]          # Only log ID 0x123
# FILTER_CAN_IDS = [0x123, 0x456]   # Only log these two IDs

# ─── CAN Mode Constants ────────────────────────────────────────────────────
GS_CAN_MODE_NORMAL = 0
GS_USB_NONE_ECHO_ID = 0xFFFFFFFF


class CanLogger:
    """Handles logging CAN frames to CSV and ASC files."""

    def __init__(self, log_dir, filter_ids=None):
        self.filter_ids = filter_ids
        self.stats = {}  # Count frames per CAN ID
        self.total_frames = 0
        self.start_datetime = datetime.now()

        # Create log directory
        os.makedirs(log_dir, exist_ok=True)

        # Generate timestamped filenames
        timestamp = self.start_datetime.strftime("%Y%m%d_%H%M%S")
        self.csv_path = os.path.join(log_dir, f"can_log_{timestamp}.csv")
        self.asc_path = os.path.join(log_dir, f"can_log_{timestamp}.asc")

        # Initialize CSV file
        if LOG_TO_CSV:
            self.csv_file = open(self.csv_path, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow([
                'Frame_Number',
                'Clock_Time',
                'Elapsed_Seconds',
                'CAN_ID_Hex',
                'CAN_ID_Dec',
                'DLC',
                'Data_Hex',
                'Data_Byte_0', 'Data_Byte_1', 'Data_Byte_2', 'Data_Byte_3',
                'Data_Byte_4', 'Data_Byte_5', 'Data_Byte_6', 'Data_Byte_7',
                'Is_Extended',
                'Is_RTR'
            ])

        # Initialize ASC file (Vector CANalyzer / SavvyCAN compatible)
        if LOG_TO_ASC:
            self.asc_file = open(self.asc_path, 'w')
            self.asc_file.write(
                f"date {self.start_datetime.strftime('%a %b %d %I:%M:%S %p %Y')}\n"
            )
            self.asc_file.write("base hex  timestamps absolute\n")
            self.asc_file.write("internal events logged\n")
            self.asc_file.write("Begin Triggerblock\n")

    def should_log(self, can_id):
        """Check if this CAN ID passes the filter."""
        if self.filter_ids is None:
            return True
        return can_id in self.filter_ids

    def log_frame(self, frame_num, clock_time, elapsed, raw_can_id, data_bytes):
        """
        Log a single CAN frame to CSV and ASC files.
        Returns (can_id, dlc, data_hex, is_extended, is_rtr) if logged, None if filtered.
        """
        # Decode flags
        is_extended = bool(raw_can_id & CAN_EFF_FLAG)
        is_rtr = bool(raw_can_id & CAN_RTR_FLAG)
        is_error = bool(raw_can_id & CAN_ERR_FLAG)

        if is_error:
            return None  # Skip error frames

        # Extract actual CAN ID
        if is_extended:
            can_id = raw_can_id & 0x1FFFFFFF
        else:
            can_id = raw_can_id & 0x7FF

        # Apply filter
        if not self.should_log(can_id):
            return None

        # Update statistics
        id_hex = f"0x{can_id:03X}" if not is_extended else f"0x{can_id:08X}"
        self.stats[id_hex] = self.stats.get(id_hex, 0) + 1
        self.total_frames += 1

        dlc = len(data_bytes)
        data_hex = ' '.join(f'{b:02X}' for b in data_bytes)

        # ── Write to CSV ────────────────────────────────────────────────
        if LOG_TO_CSV:
            # Pad data bytes to 8 columns (fill missing with empty string)
            byte_columns = [f'0x{b:02X}' for b in data_bytes]
            while len(byte_columns) < 8:
                byte_columns.append('')

            self.csv_writer.writerow([
                frame_num,
                clock_time,
                f"{elapsed:.6f}",
                id_hex,
                can_id,
                dlc,
                data_hex,
                *byte_columns,
                is_extended,
                is_rtr
            ])
            self.csv_file.flush()

        # ── Write to ASC (Vector format) ────────────────────────────────
        if LOG_TO_ASC:
            direction = "Rx"
            id_str = f"{can_id:03X}" if not is_extended else f"{can_id:08X}x"
            data_asc = ' '.join(f'{b:02X}' for b in data_bytes)
            self.asc_file.write(
                f"   {elapsed:.6f} 1  {id_str}       {direction}   d {dlc} {data_asc}\n"
            )
            self.asc_file.flush()

        return can_id, dlc, data_hex, is_extended, is_rtr

    def close(self):
        """Close all log files."""
        if LOG_TO_CSV:
            self.csv_file.close()
        if LOG_TO_ASC:
            self.asc_file.write("End Triggerblock\n")
            self.asc_file.close()

    def print_summary(self):
        """Print final statistics and file locations."""
        duration = time.time() - self.start_datetime.timestamp()

        print("")
        print("=" * 60)
        print("  📊 Logging Summary")
        print("=" * 60)
        print(f"  Duration:     {duration:.1f} seconds")
        print(f"  Total frames: {self.total_frames}")
        if duration > 0:
            print(f"  Average rate: {self.total_frames / duration:.1f} frames/sec")
        print("")

        # Per-ID breakdown
        print("  Frames per CAN ID:")
        print("  " + "─" * 35)
        for can_id, count in sorted(self.stats.items()):
            bar = "█" * min(count, 30)
            print(f"    {can_id}: {count:>6} frames  {bar}")
        print("  " + "─" * 35)

        # File locations
        print("")
        if LOG_TO_CSV:
            size = os.path.getsize(self.csv_path) if os.path.exists(self.csv_path) else 0
            print(f"  📄 CSV: {self.csv_path} ({size:,} bytes)")
        if LOG_TO_ASC:
            size = os.path.getsize(self.asc_path) if os.path.exists(self.asc_path) else 0
            print(f"  📄 ASC: {self.asc_path} ({size:,} bytes)")
        print("")


def main():
    print("=" * 60)
    print("  📄 CAN Bus Logger — Innomaker USB2CAN")
    print("=" * 60)
    print("")

    # ── Setup device ────────────────────────────────────────────────────────
    print("🔍 Scanning for USB2CAN devices...")
    devices = GsUsb.scan()

    if len(devices) == 0:
        print("❌ No USB2CAN device found!")
        return

    if DEVICE_INDEX >= len(devices):
        print(f"❌ Device [{DEVICE_INDEX}] not available.")
        return

    dev = devices[DEVICE_INDEX]
    print(f"✅ Using Device [{DEVICE_INDEX}]: {dev}")

    try:
        dev.stop()
    except Exception:
        pass

    if not dev.set_bitrate(BITRATE):
        print("❌ Failed to set bitrate.")
        return
    print(f"✅ Bitrate set to {BITRATE} bps (500 kbps)")

    dev.start(GS_CAN_MODE_NORMAL)
    print("✅ Device started in NORMAL mode")
    print("")

    # ── Initialize Logger ───────────────────────────────────────────────────
    logger = CanLogger(LOG_DIR, FILTER_CAN_IDS)

    if FILTER_CAN_IDS:
        filter_str = ', '.join(f'0x{fid:03X}' for fid in FILTER_CAN_IDS)
        print(f"🔍 Filter active: only logging IDs [{filter_str}]")
    else:
        print("🔍 No filter — logging ALL CAN IDs")

    if LOG_TO_CSV:
        print(f"📄 CSV → {logger.csv_path}")
    if LOG_TO_ASC:
        print(f"📄 ASC → {logger.asc_path}")

    print("")
    print("📥 Logging CAN frames... Press Ctrl+C to stop and save")
    print("─" * 85)
    print(
        f"  {'#':>5} | {'Clock Time':>14} | {'Elapsed':>9} | "
        f"{'ID':>10} | {'DLC':>3} | {'Data':<24} | Flags"
    )
    print("─" * 85)

    start_time = time.time()
    rx_count = 0

    try:
        while True:
            iframe = GsUsbFrame()
            if dev.read(iframe, 1):
                if iframe.echo_id == GS_USB_NONE_ECHO_ID:
                    rx_count += 1
                    clock_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    elapsed = time.time() - start_time
                    data_bytes = bytes(iframe.data[:8])

                    result = logger.log_frame(
                        rx_count, clock_time, elapsed,
                        iframe.can_id, data_bytes
                    )

                    if result:
                        can_id, dlc, data_hex, is_ext, is_rtr = result
                        id_str = f"0x{can_id:03X}" if not is_ext else f"0x{can_id:08X}"

                        flags = []
                        if is_ext:
                            flags.append("EXT")
                        if is_rtr:
                            flags.append("RTR")
                        flags_str = ','.join(flags) if flags else "STD"

                        print(
                            f"  {rx_count:>5} | "
                            f"{clock_time:>14} | "
                            f"{elapsed:>8.3f}s | "
                            f"{id_str:>10} | "
                            f"{dlc:>3} | "
                            f"{data_hex:<24} | "
                            f"{flags_str}"
                        )

    except KeyboardInterrupt:
        print("\n\n🛑 Logger stopped by user.")

    finally:
        logger.close()
        logger.print_summary()
        print("✅ All log files saved successfully!")


if __name__ == "__main__":
    main()