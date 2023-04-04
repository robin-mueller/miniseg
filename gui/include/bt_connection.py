import json
import time
import bluetooth

from threading import Lock
from collections import UserDict


class BTDeviceNotConnected(Exception):
    pass


class BTDevice(UserDict):
    def __init__(self, address: str):
        super().__init__()
        self._address = address
        self._connect_lock = Lock()
        self._connected = False
        self._socket = bluetooth.BluetoothSocket()
        self._socket.settimeout(5)
        
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.publish_data()
        
    def connect(self):
        with self._connect_lock:
            if not self._connected:
                self._socket.connect((self._address, 1))
                self._connected = True
        
    def disconnect(self):
        with self._connect_lock:
            if self._connected:
                self._socket.close()
                self._connected = False
        
    def publish_data(self):
        with self._connect_lock:
            if self._connected:
                self._socket.send(json.dumps(self.data).encode())
            else:
                raise BTDeviceNotConnected("Instance method connect() was never called!")
        
    @staticmethod
    def discover():
        nearby_devices = bluetooth.discover_devices(duration=5, lookup_names=True)
        print("Found {} devices.".format(len(nearby_devices)))
        
        for addr, name in nearby_devices:
            print(f"Adress: {addr} - Name: {name}")
        
        
if __name__ == "__main__":
    device = BTDevice("98:D3:A1:FD:34:63")
    device.connect()
    device["TEST"] = 8
    time.sleep(0.5)
    device.disconnect()
    
    # i = 0
    # while i < 10:
    #     i += 1
    #     print(device._socket.recv(1024))
    #     time.sleep(0.5)
