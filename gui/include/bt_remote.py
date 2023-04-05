import json
import time

from bluetooth import discover_devices, BluetoothSocket
from typing import Optional, Callable
from threading import Lock
from collections import UserDict
from PySide6.QtCore import QThread, Signal, QObject


class BTRemoteNotConnected(Exception):
    pass


class BTRemote(UserDict):
    class ConnectWorker(QObject):
        connected = Signal()
        connection_failed = Signal(str)
        finished = Signal()
        
        def __init__(self, connect_handle: Callable[[], None]):
            super().__init__()
            self.connect_handle = connect_handle
        
        def run(self):
            try:
                self.connect_handle()
                self.connected.emit()
            except Exception as e:
                self.connection_failed.emit(type(e).__name__)
            finally:
                self.finished.emit()
        
    def __init__(self, address: str):
        super().__init__()
        self._address = address
        self._connect_lock = Lock()
        self._connected = False
        self._socket: Optional[BluetoothSocket] = None
        self._connect_worker: Optional[BTRemote.ConnectWorker] = None
        self._connect_thread: Optional[QThread] = None
        
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.publish_data()
        
    def connect(self):
        with self._connect_lock:
            if not self._connected:
                self._socket = BluetoothSocket()
                self._socket.settimeout(5)
                self._socket.connect((self._address, 1))
                self._connected = True
    
    # noinspection PyUnresolvedReferences
    def async_connect(self, on_connected_handle: Callable[[], None], on_connection_failed_handle: Callable[[str], None]):
        self._connect_worker = BTRemote.ConnectWorker(self.connect)
        self._connect_worker.connected.connect(on_connected_handle)
        self._connect_worker.connection_failed.connect(on_connection_failed_handle)
        
        self._connect_thread = QThread()
        self._connect_worker.moveToThread(self._connect_thread)
        self._connect_thread.started.connect(self._connect_worker.run)
        self._connect_worker.finished.connect(self._connect_thread.quit)
        self._connect_worker.finished.connect(self._connect_worker.deleteLater)
        self._connect_thread.finished.connect(self._connect_thread.deleteLater)
        
        self._connect_thread.start()
        
    def disconnect(self):
        with self._connect_lock:
            if self._connected:
                self._socket.close()
                self._socket = None
                self._connected = False
        
    def publish_data(self):
        with self._connect_lock:
            if self._connected:
                try:
                    self._socket.send(json.dumps(self.data).encode())
                except TimeoutError as e:
                    self.disconnect()
                    raise e
            else:
                raise BTRemoteNotConnected("Instance method connect() was never called!")
        
    @staticmethod
    def discover():
        nearby_devices = discover_devices(duration=5, lookup_names=True)
        print("Found {} devices.".format(len(nearby_devices)))
        
        for addr, name in nearby_devices:
            print(f"Adress: {addr} - Name: {name}")
        
        
if __name__ == "__main__":
    device = BTRemote("98:D3:A1:FD:34:63")
    device.connect()
    device["TEST"] = 8
    time.sleep(0.5)
    device.disconnect()
    
    # i = 0
    # while i < 10:
    #     i += 1
    #     print(device._socket.recv(1024))
    #     time.sleep(0.5)
