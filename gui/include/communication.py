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


class InterfaceDefinition(UserDict):
    # Maps the types that are allowed to be specified in the interface json file to Python types
    TYPE_TRANSLATION = {
        "char[]": str,
        "bool": bool,
        "float": float,
        "double": float,
        "int": int
    }

    class MissingCorrespondingType(Exception):
        pass

    def __init__(self, interface_json: dict[str, str | dict], /, **kwargs):
        if not isinstance(interface_json, dict):
            raise TypeError(f"Wrong type of interface_json: {type(interface_json)}. "
                            f"The interface must be defined as an arbitrarily nested dict with string values that specify the data type.")
        super().__init__(interface_json, **kwargs)

    def __setitem__(self, key, val):
        if not isinstance(key, str):
            raise TypeError(f"key must be a string but provided was {type(key)}.")
        if isinstance(val, str):
            if val not in self.TYPE_TRANSLATION:
                raise self.MissingCorrespondingType(f"Type translation for '{val}' is missing.")
            super().__setitem__(key, self.TYPE_TRANSLATION[re.sub(r'\d+', '', val)])
        elif isinstance(val, dict):
            super().__setitem__(key, InterfaceDefinition(val))
        elif isinstance(val, type):
            super().__setitem__(key, val)
        else:
            raise TypeError(f"val must be a type, string or dict but provided was {type(val)}.")


class Interface(UserDict):
    """
    A thread safe dict-like object that acts like a runtime validated buffer for incoming and outgoing data.
    """

    # This specifies the cases upon setting a value where conversion from set_type to defined_type is explicitly allowed.
    # A single or multiple types may be specified inside a list.
    # Format {set_type: list[defined_type])
    _CONVERSION_WHITELIST = {
        int: [float]
    }

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

    def __init__(self, interface_definition: InterfaceDefinition, *add_members: tuple[str, type]):
        super().__init__()
        self._access_lock = RLock()
        self._interface_def: UserDict[str, type | InterfaceDefinition] = interface_definition

        # Add optional additional members
        self._interface_def.update({name: t for name, t in add_members})

        for key, val in self._interface_def.items():
            if isinstance(val, InterfaceDefinition):
                self.data[key] = Interface(val)
            elif isinstance(val, type):
                self.data[key] = val()
            else:
                raise TypeError(f"Wrong value type: {type(val)}! Only InterfaceDefinition and types allowed.")

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

                defined_type = self._interface_def[key]
                set_type = type(value)
                if set_type != defined_type and defined_type not in self._CONVERSION_WHITELIST.get(set_type, []):
                    raise self.ConversionError(f"Type of {value=} is {type(value)} but defined was {defined_type}. Interface values must be loyal to their types defined at initialization.")
                try:
                    converted_val = defined_type(value)
                except ValueError:
                    raise self.ConversionError(f"Could no convert {value=} of type {type(value)} for key '{key}' to {self._interface_def[key]}.")
                else:
                    super().__setitem__(key, converted_val)
                    return

            elif isinstance(key, tuple):  # If dict is accessed using multiple keys
                d = self.__getitem__(key[:-1])
                if isinstance(d, Interface):
                    d[key[-1]] = value
                    return
                raise TypeError(f"Key {key[-2]} doesn't point to another instance of {type(self)}.")

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

    def __init__(self, address: str, interface_json_path: Path, connect_timeout_sec: float = 5.0, rx_chunk_size: int = 4096, allowed_rx_bufferbloat: int = 1024):
        self._address = address
        self._conn_timeout = connect_timeout_sec
        self._rx_chunk_size = rx_chunk_size
        self._allowed_rx_bufferbloat = allowed_rx_bufferbloat
        self._rx_buffer = bytearray()
        self._connect_lock = RLock()  # Needs to be reentrant because of the except statement in self.publish()
        self._connected = False
        self._socket: BluetoothSocket | None = None

        with interface_json_path.open() as interface_file:
            interface_json = json.load(interface_file)
            try:
                to_device_def = InterfaceDefinition(interface_json["TO_DEVICE"])
                from_device_def = InterfaceDefinition(interface_json["FROM_DEVICE"])
            except (TypeError, KeyError):
                raise self.InvalidDataError("Base key(s) not found! "
                                            "Specifiers for the data interface to and from the device have to be listed under the keys 'TO_DEVICE' and 'FROM_DEVICE' respectively.")
            else:
                self._tx_interface = Interface(to_device_def)
                self._rx_interface = Interface(from_device_def, ("msg", str))

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

    def send(self, write: dict = None, /, **kwargs):
        if write:
            self.tx_interface.update(write)
        if kwargs:
            self.tx_interface.update(kwargs)
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
                    self._socket.settimeout(1)

                    # Receive header that contains start bit and message length
                    while True:
                        b = self._socket.recv(self._rx_chunk_size)
                        if b == b'':  # If socket was closed from other side
                            return b''
                        self._rx_buffer.extend(b)
                        msg_start = self._rx_buffer.find(self.MSG_START_TOKEN)
                        if msg_start != -1:
                            break
                    self._rx_buffer = self._rx_buffer[msg_start:]  # Remove msg start token from buffer

                    while len(self._rx_buffer) < self.MSG_HEADER_LEN:
                        b = self._socket.recv(self._rx_chunk_size)
                        if b == b'':  # If socket was closed from other side
                            return b''
                        self._rx_buffer.extend(b)
                    msg_len = int.from_bytes(self._rx_buffer[self.MSG_START_TOKEN_LEN:self.MSG_START_TOKEN_LEN + self.MSG_SIZE_HINT_LEN], 'little')
                    self._rx_buffer = self._rx_buffer[self.MSG_HEADER_LEN:]  # Remove msg header from buffer

                    # Receive actual message
                    while len(self._rx_buffer) < msg_len:
                        b = self._socket.recv(self._rx_chunk_size)
                        if b == b'':  # If socket was closed from other side
                            return b''
                        self._rx_buffer.extend(b)
                    msg = self._rx_buffer[:msg_len]
                    self._rx_buffer = self._rx_buffer[msg_len:]  # Remove received message from buffer

                    if len(self._rx_buffer) > self._allowed_rx_bufferbloat:
                        warnings.warn(f"Bufferbloat is very large which means that incoming messages aren't processed fast enough. "
                                      f"After message receive {len(self._rx_buffer)} bytes were left over in the buffer.", RuntimeWarning)
                    return bytes(msg)
                return b''
            else:
                raise self.NotConnectedError("Cannot receive when the socket is not connected!")

    def deserialize(self, received: bytes):
        try:
            data = json.loads(received.decode())
        except ValueError:  # Incomplete JSON message, continue to accumulate incoming data
            raise self.InvalidDataError(f"Could not interprete received data: {received}") from None
        else:
            self.rx_interface.update(data)

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
