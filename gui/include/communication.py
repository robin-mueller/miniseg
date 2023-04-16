import json
import time
import re
import warnings
import select

from functools import reduce
from pathlib import Path
from bluetooth import discover_devices, BluetoothSocket
from threading import RLock
from collections import UserDict


class Interface(UserDict):
    """
    A thread safe dict-like object that acts like a runtime validated buffer for incoming and outgoing data.
    """

    # Maps the types that are allowed to be specified in the interface json file to Python types
    VALID_TYPES = {
        "char[]": str,
        "bool": bool,
        "float": float,
        "double": float,
        "int": int
    }

    class UndefinedType:
        def __init__(self, *args, **kwargs):
            raise ValueError

    class ConversionError(Exception):
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

    def __init__(self, interface_definition: dict[str, str | dict], *add_members: tuple[str, type]):
        if not isinstance(interface_definition, dict):
            raise TypeError(f"Wrong type of interface_def: {type(interface_definition)}. The interface has to be defined as a dict with string or dicts as values.")
        super().__init__()
        self._access_lock = RLock()

        # Translate interface def
        self._interface_def: dict[str, type | dict] = {
            name: self.VALID_TYPES.get(re.sub(r'\d+', '', val), self.UndefinedType) if isinstance(val, str) else val
            for name, val in interface_definition.items()
        }
        # Add optional additional members
        self._interface_def.update({name: t for name, t in add_members})

        self.data = {}
        for key, val in interface_definition.items():
            if isinstance(val, str):
                self.data[key] = None
            elif isinstance(val, dict):
                self.data[key] = Interface(val)
            else:
                raise TypeError(f"Wrong value type for a key: {type(val)}! Only strings and dicts allowed.")

    @property
    def definition(self):
        return self._interface_def

    def __getitem__(self, key: str | tuple):
        with self._access_lock:
            if isinstance(key, str):  # If dict is accessed using a single key
                try:
                    return super().__getitem__(key)
                except KeyError:
                    raise self.UnmatchedKeyError(key, self) from None
            elif isinstance(key, tuple):  # If dict is accessed using multiple keys
                return reduce(lambda d, k: d[k], key, self)
            else:
                raise TypeError(f"Argument 'key' must be a string or a tuple of strings not {type(key)}.")

    def __setitem__(self, key: str | tuple, value):
        with self._access_lock:
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
                try:
                    converted_val = self._interface_def[key](value)
                except ValueError:
                    raise self.ConversionError(f"Could no convert value {value=} of type {type(value)} for key '{key}' to {self._interface_def[key]}.")
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

    MSG_START_TOKEN = b'$'
    MSG_START_TOKEN_LEN = len(MSG_START_TOKEN)
    MSG_SIZE_HINT_LEN = 2
    MSG_HEADER_LEN = MSG_START_TOKEN_LEN + MSG_SIZE_HINT_LEN

    def __init__(self, address: str, interface_json: Path, connect_timeout_sec: float = 5.0, rx_chunk_size: int = 4096):
        self._address = address
        self._conn_timeout = connect_timeout_sec
        self._rx_chunk_size = rx_chunk_size
        self._connect_lock = RLock()  # Needs to be reentrant because of the except statement in self.publish()
        self._connected = False
        self._socket: BluetoothSocket | None = None

        with interface_json.open() as interface_file:
            interface_specifiers = json.load(interface_file)
            try:
                self._tx_interface = Interface(interface_specifiers["TO_DEVICE"])
                self._rx_interface = Interface(interface_specifiers["FROM_DEVICE"], ("msg", str))
            except (TypeError, KeyError):
                raise self.InvalidDataError("Base key(s) not found! "
                                            "Specifiers for the data interface to and from the device have to be listed under the keys 'TO_DEVICE' and 'FROM_DEVICE' respectively.")

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
                msg_bytes = json.dumps(self.tx_interface, cls=Interface.JSONEncoder, separators=(',', ':')).encode()
                msg_bytes = self.MSG_START_TOKEN + len(msg_bytes).to_bytes(2, 'little') + msg_bytes
                try:
                    self._socket.sendall(msg_bytes)
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
                    self._socket.settimeout(1)

                    # Receive header that contains start bit and message length
                    while True:
                        b = self._socket.recv(self._rx_chunk_size)
                        if b == b'':  # If socket was closed from other side
                            return b''
                        buffer.extend(b)
                        msg_start = buffer.find(self.MSG_START_TOKEN)
                        if msg_start != -1:
                            break
                    buffer = buffer[msg_start:]
                    while len(buffer) < self.MSG_HEADER_LEN:
                        b = self._socket.recv(self._rx_chunk_size)
                        if b == b'':  # If socket was closed from other side
                            return b''
                        buffer.extend(b)
                    msg_len = int.from_bytes(buffer[self.MSG_START_TOKEN_LEN:][:self.MSG_SIZE_HINT_LEN], 'little')
                    msg = buffer[self.MSG_HEADER_LEN:]

                    # Receive actual message
                    while len(msg) < msg_len:
                        b = self._socket.recv(self._rx_chunk_size)
                        if b == b'':  # If socket was closed from other side
                            return b''
                        msg.extend(b)
                    leftover = msg[msg_len:]
                    if len(leftover) != 0:
                        warnings.warn(f"Can't keep up with arriving data. {len(leftover)} bytes ({leftover}) arrived earlier than they could be processed and are being dumped!", RuntimeWarning)
                    return bytes(msg)
                return b''
            else:
                raise self.NotConnectedError("Cannot receive when the socket is not connected!")

    def deserialize(self, received: bytes):
        try:
            json_msg = json.loads(received.decode())
        except ValueError:  # Incomplete JSON message, continue to accumulate incoming data
            raise self.InvalidDataError(f"Could not interprete received data: {received}") from None
        else:
            return json_msg

    @staticmethod
    def discover():
        nearby_devices = discover_devices(duration=5, lookup_names=True)
        print(f"Found {len(nearby_devices)} devices:")
        for addr, name in nearby_devices:
            print(f"Adress: {addr} - Name: {name}")


if __name__ == "__main__":
    device = BTDevice("98:D3:A1:FD:34:63", Path(__file__).parent.parent.parent / "interface.json")
    device.tx_interface["controller_state"] = True
    device.connect()
    device.send()
    time.sleep(0.5)
    device.disconnect()

    # i = 0
    # while i < 10:
    #     i += 1
    #     print(device._socket.recv(1024))
    #     time.sleep(0.5)
