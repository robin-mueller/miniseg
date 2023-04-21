import json
import time
import warnings
import select

from pathlib import Path
from bluetooth import discover_devices, BluetoothSocket
from include.communication.interface import InterfaceDefinition, Interface
from include.plotting import StampedData


class BTDevice:
    class NotConnectedError(Exception):
        pass

    class InvalidDataError(Exception):
        pass

    MSG_START_TOKEN = b'$'
    MSG_START_TOKEN_LEN = len(MSG_START_TOKEN)
    MSG_SIZE_HINT_LEN = 2
    MSG_HEADER_LEN = MSG_START_TOKEN_LEN + MSG_SIZE_HINT_LEN

    def __init__(self, address: str, rx_interface_def: InterfaceDefinition, tx_interface_def: InterfaceDefinition, connect_timeout_sec: float = 5.0, rx_chunk_size: int = 4096, allowed_rx_bufferbloat: int = 1024):
        self._address = address
        self._conn_timeout = connect_timeout_sec
        self._rx_chunk_size = rx_chunk_size
        self._allowed_rx_bufferbloat = allowed_rx_bufferbloat
        self._rx_buffer = bytearray()
        self._connected = False
        self._socket: BluetoothSocket | None = None
        self._rx_interface = Interface(rx_interface_def)
        self._tx_interface = Interface(tx_interface_def)

    @property
    def tx_interface(self):
        return self._tx_interface

    @property
    def rx_interface(self):
        return self._rx_interface

    def connect(self):
        if not self._connected:
            self._socket = BluetoothSocket()
            self._socket.settimeout(self._conn_timeout)
            self._socket.connect((self._address, 1))
            self._connected = True

    def disconnect(self):
        if self._connected:
            self._socket.close()
            self._socket = None
            self._connected = False

    def send(self, write: dict = None, /, **kwargs):
        if write:
            self.tx_interface.update(write)
        if kwargs:
            self.tx_interface.update(kwargs)
        if self._connected:
            msg_bytes = json.dumps(self.tx_interface, cls=Interface.JSONEncoder, separators=(',', ':')).encode()
            msg_bytes = self.MSG_START_TOKEN + len(msg_bytes).to_bytes(2, 'big') + msg_bytes
            try:
                self._socket.sendall(msg_bytes)
            except Exception as e:
                raise e
        else:
            raise self.NotConnectedError("Cannot send when device is not connected via Bluetooth!")

    def receive(self):
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
                msg_len = int.from_bytes(self._rx_buffer[self.MSG_START_TOKEN_LEN:self.MSG_START_TOKEN_LEN + self.MSG_SIZE_HINT_LEN], 'big')
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
            raise self.NotConnectedError("Cannot receive when device is not connected via Bluetooth!")

    def deserialize(self, received: bytes):
        try:
            data = json.loads(received.decode())
        except ValueError:  # Incomplete JSON message, continue to accumulate incoming data
            raise self.InvalidDataError(f"Could not interprete received data: {received}") from None
        else:
            self.rx_interface.update({k: StampedData(v, data["ts"]) for k, v in data.items()})

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
