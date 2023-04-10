import json
import time
import re
import select

from functools import reduce
from pathlib import Path
from bluetooth import discover_devices, BluetoothSocket
from typing import NewType
from threading import RLock
from collections import UserDict


class Interface(UserDict):
    """
    A thread safe dict-like object that acts like a runtime validated buffer for incoming and outgoing data.
    """

    # Maps the types that are allowed to specify in the interface file to Python types
    _valid_type_map = {
        'char[]': str,
        'bool': bool,
        'float': float,
        'int': int
    }
    _UNDEFINED_TYPE = NewType('UndefinedType', None)

    class ConversionError(Exception):
        pass

    class JsonFormatError(Exception):
        pass

    class UnmatchedKeyError(Exception):
        def __init__(self, key: str, available_keys: list | dict | UserDict):
            super().__init__(f"Key '{key}' has no match with the specified interface keys {list(available_keys)}.")

    class SetItemNotAllowedError(Exception):
        def __init__(self, key: str):
            super().__init__(
                f"Key '{key}' doesn't point to a value, but rather to a nested instance of {Interface}. "
                f"Calling __setitem__() is only allowed for a key on the lowest level, hence only for keys that point to values. "
                f"Otherwise protected {Interface.__name__} objects would be overwritten!")

    class JSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, Interface):
                return obj.data
            return super().default(obj)

    def __init__(self, interface_def: dict[str, str | dict]):
        if not isinstance(interface_def, dict):
            raise TypeError(f"Wrong type of interface_def: {type(interface_def)}. "
                            f"The interface has to be defined as a dict with values of strings and possibly nested dicts.")
        super().__init__()
        self._lock = RLock()
        self._interface_def = interface_def
        self.data = self._generate_initial_dict()

    def _generate_initial_dict(self):
        result = {}
        for key, val in self._interface_def.items():
            if isinstance(val, str):
                result[key] = None
            elif isinstance(val, dict):
                result[key] = Interface(val)
            else:
                raise TypeError(f"Wrong value type for a key: {type(val)}! Only strings and dicts allowed.")
        return result

    def __getitem__(self, key: str | tuple[str]):
        with self._lock:
            if isinstance(key, str):  # If dict is accessed using a single key
                try:
                    return super().__getitem__(key)
                except KeyError:
                    raise self.UnmatchedKeyError(key, self) from None
            elif isinstance(key, tuple):  # If dict is accessed using multiple keys
                return reduce(lambda d, k: d[k], key, self)
            else:
                raise TypeError(f"Argument 'key' must be a string or a tuple of strings not {type(key)}.")

    def __setitem__(self, key: str | tuple[str], value):
        with self._lock:
            if isinstance(key, str):  # If dict is accessed using a single key
                if key not in self:
                    raise self.UnmatchedKeyError(key, self)
                if isinstance(self.__getitem__(key), Interface):
                    if isinstance(value, dict):
                        # Parse dict and try to assign values recursively
                        for k, v in value.items():
                            self.__getitem__(key)[k] = v
                        return
                    else:
                        raise self.SetItemNotAllowedError(key)
                defined_type = self._valid_type_map.get(re.sub(r'\d+', '', self._interface_def[key]), self._UNDEFINED_TYPE)
                try:
                    converted_val = defined_type(value)
                except ValueError:
                    raise self.ConversionError(f"Could no convert value to defined type: "
                                               f"Value type for key '{key}' was defined as '{self._interface_def[key]}' which corresponds to {defined_type} "
                                               f"but provided was {type(value)} ({value=}).")
                else:
                    super().__setitem__(key, converted_val)
            elif isinstance(key, tuple):  # If dict is accessed using multiple keys
                d = self.__getitem__(key[:-1])
                if isinstance(d, Interface):
                    d[key[-1]] = value
                else:
                    raise TypeError(f"Key {key[-2]} doesn't point to another instance of {type(self)}!")
            else:
                raise TypeError(f"Argument 'key' must be a string or a tuple of strings not {type(key)}.")


class BTDevice:
    class NotConnectedError(Exception):
        pass

    class InvalidDataError(Exception):
        pass

    def __init__(self, address: str, interface_json: Path, connect_timeout_sec: float = 5.0, receive_timeout_sec: float = 1.0, rx_chunk_size: int = 1024):
        self._address = address
        self._conn_timeout = connect_timeout_sec
        self._recv_timeout = receive_timeout_sec
        self._rx_chunk_size = rx_chunk_size
        self._connect_lock = RLock()  # Needs to be reentrant because of the except statement in self.publish()
        self._connected = False
        self._socket: BluetoothSocket | None = None

        with interface_json.open() as interface_file:
            interface_specifiers = json.load(interface_file)
            try:
                self._tx_interface = Interface(interface_specifiers["to_device"])
                self._rx_interface = Interface(interface_specifiers["from_device"])
            except (TypeError, KeyError):
                raise Interface.JsonFormatError("Base key(s) not found! "
                                                "Specifiers for the data interface to and from the device have to be listed under the keys 'to_device' and 'from_device' respectively.")

    @property
    def tx_interface(self):
        return self._tx_interface

    @property
    def rx_interface(self):
        return self._rx_interface

    def connect(self):
        with self._connect_lock:
            if not self._connected:
                self._socket = BluetoothSocket()
                self._socket.settimeout(self._conn_timeout)
                self._socket.connect((self._address, 1))
                self._connected = True

    def disconnect(self):
        with self._connect_lock:
            if self._connected:
                self._socket.close()
                self._socket = None
                self._connected = False

    def send(self, write: dict = None):
        if write:
            self.tx_interface.update(write)
        with self._connect_lock:
            if self._connected:
                try:
                    self._socket.sendall(
                        json.dumps(self.tx_interface, cls=Interface.JSONEncoder, separators=(',', ':')).encode()
                    )
                except TimeoutError as e:
                    self.disconnect()
                    raise e
            else:
                raise self.NotConnectedError("Instance method connect() was never called!")

    def receive(self):
        with self._connect_lock:
            if self._connected:
                if select.select([self._socket], [], [], 0)[0]:  # Check for available data
                    buffer = bytearray()
                    self._socket.settimeout(self._recv_timeout)
                    while True:
                        buffer.extend(self._socket.recv(self._rx_chunk_size))
                        try:
                            json_msg = json.loads(buffer.decode())
                        except ValueError:  # Incomplete JSON message, continue to accumulate incoming data
                            continue
                        except TimeoutError:
                            raise self.InvalidDataError(f"Could not interprete received data: {buffer.decode()}")
                        else:
                            self.rx_interface.update(json_msg)
                            break
                    print(self.rx_interface.data)
                    return True
                return False
            else:
                raise self.NotConnectedError("Cannot receive when the socket is not connected!")

    @staticmethod
    def discover():
        nearby_devices = discover_devices(duration=5, lookup_names=True)
        print(f"Found {len(nearby_devices)} devices:")
        for addr, name in nearby_devices:
            print(f"Adress: {addr} - Name: {name}")


if __name__ == "__main__":
    device = BTDevice("98:D3:A1:FD:34:63", Path(__file__).parent.parent.parent / "interface.json")
    device.tx_interface["controller_state"] = True
    device.tx_interface["a1", "b1"] = 5.5
    device.connect()
    print("Send: " + str(device.tx_interface))
    device.send()
    time.sleep(0.5)
    device.disconnect()

    # i = 0
    # while i < 10:
    #     i += 1
    #     print(device._socket.recv(1024))
    #     time.sleep(0.5)
