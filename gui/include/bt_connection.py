# 98:D3:A1:FD:34:63

import bluetooth

nearby_devices = bluetooth.discover_devices(duration=3, lookup_names=True)
print("Found {} devices.".format(len(nearby_devices)))

for addr, name in nearby_devices:
    print("  {} - {}".format(addr, name))
