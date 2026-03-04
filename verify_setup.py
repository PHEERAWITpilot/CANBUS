"""
Debug script to check if libusb can see the USB2CAN devices at all.
"""

# Step 1: Check if libusb/pyusb works
print("=" * 50)
print("  USB2CAN Debug Tool")
print("=" * 50)
print()

try:
    import usb.core
    import usb.util
    print("✅ pyusb imported successfully")
except ImportError:
    print("❌ pyusb not installed. Run: pip install pyusb")
    exit()

# Step 2: Check libusb backend
try:
    import usb.backend.libusb1 as libusb1
    backend = libusb1.get_backend()
    if backend is None:
        print("❌ libusb backend NOT found!")
        print("   → You need to copy libusb-1.0.dll to C:\\Windows\\System32")
        print("   → Download from: https://sourceforge.net/projects/libusb/files/libusb-1.0/libusb-1.0.20/")
    else:
        print(f"✅ libusb backend found: {backend}")
except Exception as e:
    print(f"❌ libusb error: {e}")

# Step 3: Search for Innomaker USB2CAN devices (Vendor ID: 0x1D50, Product ID: 0x606F)
print()
print("🔍 Searching for ALL USB devices...")
all_devices = list(usb.core.find(find_all=True))
print(f"   Found {len(all_devices)} total USB devices")

print()
print("🔍 Searching for Innomaker USB2CAN (VID=1D50, PID=606F)...")
can_devices = list(usb.core.find(find_all=True, idVendor=0x1D50, idProduct=0x606F))

if len(can_devices) == 0:
    print("❌ No USB2CAN devices found via pyusb!")
    print()
    print("   Possible causes:")
    print("   1. libusb-1.0.dll is missing from System32")
    print("   2. Zadig driver needs to be reinstalled")
    print("   3. Devices are not plugged in")
    print()
    print("   All USB devices seen:")
    for d in all_devices:
        try:
            print(f"     VID={d.idVendor:04X} PID={d.idProduct:04X} - {usb.util.get_string(d, d.iProduct) if d.iProduct else 'Unknown'}")
        except Exception:
            print(f"     VID={d.idVendor:04X} PID={d.idProduct:04X}")
else:
    print(f"✅ Found {len(can_devices)} USB2CAN device(s)!")
    for i, d in enumerate(can_devices):
        print(f"   Device [{i}]: VID={d.idVendor:04X} PID={d.idProduct:04X}")

# Step 4: Try gs_usb scan
print()
print("🔍 Trying gs_usb.scan()...")
try:
    from gs_usb.gs_usb import GsUsb
    devs = GsUsb.scan()
    print(f"   gs_usb found: {len(devs)} device(s)")
except Exception as e:
    print(f"   ❌ gs_usb error: {e}")