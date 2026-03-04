CANBUS Setup Guide (Windows)

1) Environment setup
- Open PowerShell in this project folder.
- Install Python dependency:
  pip install libusb
- After setup is finished, run this to confirm everything is ready:
  python verify_setup.py

Fix 1 — Install the libusb DLL
The gs_usb library needs libusb-1.0.dll to communicate with USB devices on Windows.
Run:
  pip install libusb
Then test:
  python verify_setup.py
If it still shows 0 devices, continue to Fix 2.

Fix 2 — Manually copy libusb DLL
1. Download:
   https://sourceforge.net/projects/libusb/files/libusb-1.0/libusb-1.0.20/libusb-1.0.20.7z/download
2. Extract the 7z file (7-Zip/WinRAR both work).
3. Copy the correct DLL to System32 (run as Administrator):
   Source (64-bit): MS64\dll\libusb-1.0.dll
   Destination: C:\Windows\System32\libusb-1.0.dll
4. Test again:
   python verify_setup.py

2) Board physical connection
- CanHigh(pin7) --> CanHigh(pin7)
- CanLow(pin2)  --> CanLow(pin2)
- Ground        --> Ground

3) External port connection (your setup)
- CANH   --> PIN7
- CANL   --> PIN2
- CANGND --> GND
