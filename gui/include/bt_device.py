import json
import time

from functools import reduce
from pathlib import Path
from bluetooth import discover_devices, BluetoothSocket
from typing import Optional, Callable
from threading import Lock
from collections import UserDict
from PySide6.QtCore import QThread, Signal, QObject


class InterfaceBuffer(UserDict):
    _valid_value_types = [float, int, str, bool]

    class JsonFormatError(Exception):
        pass

    class UnmatchedKeyError(Exception):
        def __init__(self, key, available_keys):
            super().__init__(f"Key '{key}' has no match with the specified interface keys {list(available_keys)}.")

    class SetItemNotAllowedError(Exception):
        def __init__(self, key):
            super().__init__(f"Calling __setitem__() is only allowed on the lowest level of an InterfaceDict instance, hence only on keys that point to values! "
                             f"Key '{key}' doesn't point to a value, but rather to a nested InterfaceDict instance.")

    class JSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, InterfaceBuffer):
                return obj.data
            elif isinstance(obj, dict):
                return {key: self.default(value) for key, value in obj.items()}
            return super().default(obj)

    def __init__(self, interface_keys: list[str | dict]):
        assert isinstance(interface_keys, list), TypeError(f"Wrong type of specifier_keys: {type(interface_keys)}. "
                                                           f"Specifier keys have to be defined inside a list. The list can contain strings and dictionaries.")
        super().__init__()
        self.data = self._generate_initial_dict(interface_keys)
        self._interface_keys = interface_keys

    @staticmethod
    def _generate_initial_dict(keys: list):
        result = {}
        for key in keys:
            if isinstance(key, str):
                result[key] = None
            elif isinstance(key, dict):
                for k, v in key.items():
                    assert isinstance(v, list), "All specifiers must be defined inside a list!"
                    result[k] = InterfaceBuffer(v)
            else:
                raise TypeError("Objects inside the specifier key list must be strings or dictionaries!")
        return result

    def __getitem__(self, key: str | tuple[str]):
        if isinstance(key, str):  # If dict is accessed using a single key
            try:
                return super().__getitem__(key)
            except KeyError:
                raise self.UnmatchedKeyError(key, self._interface_keys) from None
        elif isinstance(key, tuple):  # If dict is accessed using multiple keys
            return reduce(UserDict.__getitem__, key, self)
        else:
            raise TypeError(f"Argument 'key' must be a string or a tuple of strings not {type(key)}")

    def __setitem__(self, key: str | tuple, value):
        if isinstance(key, str):  # If dict is accessed using a single key
            assert any([isinstance(value, t) for t in self._valid_value_types]), TypeError(f"Value type has to be one of {self._valid_value_types}.")
            if isinstance(self.__getitem__(key), InterfaceBuffer):
                raise self.SetItemNotAllowedError(key)
            super().__setitem__(key, value)
        elif isinstance(key, tuple):  # If dict is accessed using multiple keys
            d = self.__getitem__(key[:-1])
            if isinstance(d, InterfaceBuffer) and key[-1] in d:
                d[key[-1]] = value
            else:
                raise self.UnmatchedKeyError(key, self._interface_keys)
        else:
            raise TypeError(f"Argument 'key' must be a string or a tuple of strings not {type(key)}")


class BTDevice:
    class NotConnectedError(Exception):
        pass

    class _ConnectWorker(QObject):
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

    def __init__(self, address: str, interface_json: Path):
        self._address = address
        self._connect_lock = Lock()
        self._connected = False
        self._socket: Optional[BluetoothSocket] = None
        self._connect_worker: Optional[BTDevice._ConnectWorker] = None
        self._connect_thread: Optional[QThread] = None

        with interface_json.open() as interface_file:
            interface_specifiers = json.load(interface_file)
            try:
                self._tx_buf = InterfaceBuffer(interface_specifiers["to_device"])
                self._rx_buf = InterfaceBuffer(interface_specifiers["from_device"])
            except (TypeError, KeyError):
                raise InterfaceBuffer.JsonFormatError("Base key(s) not found! "
                                                      "Specifiers for the data interface to and from the device have to be listed under the keys 'to_device' and 'from_device' respectively.")

    @property
    def tx_buffer(self):
        return self._tx_buf

    @property
    def rx_buffer(self):
        return self._rx_buf

    def connect(self):
        with self._connect_lock:
            if not self._connected:
                self._socket = BluetoothSocket()
                self._socket.settimeout(5)
                self._socket.connect((self._address, 1))
                self._connected = True

    # noinspection PyUnresolvedReferences
    def async_connect(self, on_connected_handle: Callable[[], None], on_connection_failed_handle: Callable[[str], None]):
        self._connect_worker = self._ConnectWorker(self.connect)
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
                    self._socket.send(json.dumps(self.tx_buffer, cls=InterfaceBuffer.JSONEncoder).encode())
                except TimeoutError as e:
                    self.disconnect()
                    raise e
            else:
                raise self.NotConnectedError("Instance method connect() was never called!")

    @staticmethod
    def discover():
        nearby_devices = discover_devices(duration=5, lookup_names=True)
        print("Found {} devices.".format(len(nearby_devices)))

        for addr, name in nearby_devices:
            print(f"Adress: {addr} - Name: {name}")


if __name__ == "__main__":
    device = BTDevice("98:D3:A1:FD:34:63", Path(__file__).parent.parent.parent / "interface.json")
    device.connect()
    device.tx_buffer["controller_state"] = True
    device.publish_data()
    time.sleep(0.5)
    device.disconnect()

    # i = 0
    # while i < 10:
    #     i += 1
    #     print(device._socket.recv(1024))
    #     time.sleep(0.5)
