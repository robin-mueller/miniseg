import time
import json
import warnings
import select
import configuration as config

from bluetooth import discover_devices, BluetoothSocket
from ..helper import PROGRAM_START_TIMESTAMP, program_uptime
from .interface import DataInterface, DataInterfaceDefinition, JsonInterfaceReader

INTERFACE_JSON = JsonInterfaceReader(config.JSON_INTERFACE_DEFINITION_PATH)


class ReceiveInterface(DataInterface):
    STATUS_MESSAGE_KEY = "msg"
    DEFINITION = DataInterfaceDefinition((STATUS_MESSAGE_KEY, str), **INTERFACE_JSON.from_device)

    def __init__(self):
        super().__init__(self.DEFINITION, lambda: self._last_receive_ts - PROGRAM_START_TIMESTAMP)
        self._last_receive_ts = 0

    def update_receive_time(self):
        self._last_receive_ts = time.perf_counter()

    @property
    def status_message(self):
        return self.__getitem__(self.STATUS_MESSAGE_KEY)


class TransmitInterface(DataInterface):
    DEFINITION = DataInterfaceDefinition(**INTERFACE_JSON.to_device)

    def __init__(self):
        super().__init__(self.DEFINITION, program_uptime)


class BluetoothDevice:
    MSG_START_TOKEN = b'$'
    MSG_START_TOKEN_LEN = len(MSG_START_TOKEN)
    MSG_SIZE_HINT_LEN = 2
    MSG_HEADER_LEN = MSG_START_TOKEN_LEN + MSG_SIZE_HINT_LEN
    CONNECT_TIMEOUT_SEC = 5.0
    RX_CHUNK_SIZE = 4096
    ALLOWED_RX_BUFFERBLOAT = 1024

    class NotConnectedError(Exception):
        pass

    class InvalidDataError(Exception):
        pass

    def __init__(self, address: str):
        self._address = address
        self._rx_buffer = bytearray()
        self._connected = False
        self._socket: BluetoothSocket | None = None
        self._rx_data = ReceiveInterface()
        self._tx_data = TransmitInterface()

    @property
    def tx_data(self):
        return self._tx_data

    @property
    def rx_data(self):
        return self._rx_data

    def connect(self):
        if not self._connected:
            self._socket = BluetoothSocket()
            self._socket.settimeout(self.CONNECT_TIMEOUT_SEC)
            self._socket.connect((self._address, 1))
            self._connected = True

    def disconnect(self):
        if self._connected:
            self._socket.close()
            self._socket = None
            self._connected = False

    def send(self, key: str | tuple = None, **data):
        """
        Sends data to the device.

        :param key: The key referring to the data stored inside the transmit interface object. Any subordinate data will be sent. That also includes nested data.
        :param data: Keyword arguments specifying transmit data inline. The transmit interface object will be updated with the values specified before data is sent.
        """
        if self._connected:
            if data:
                self._tx_data.update(data)  # Update tx data interface. This simultaneously verifies that the data is consistent with the interface.
            if key:
                data.update(self._tx_data[key])

            # Send data specified in the arguments
            json_data = json.dumps(data, separators=(',', ':'), cls=DataInterface.JSONEncoder).encode()
            packet = self.MSG_START_TOKEN + len(json_data).to_bytes(2, "big") + json_data

            # Send the packet
            self._socket.sendall(packet)
        else:
            raise self.NotConnectedError("Cannot send when device is not connected via Bluetooth!")

    def receive(self):
        if self._connected:
            if select.select([self._socket], [], [], 0)[0]:  # Check for available data
                self._socket.settimeout(1)

                # Receive header that contains start bit and message length
                while True:
                    b = self._socket.recv(self.RX_CHUNK_SIZE)
                    if b == b'':  # If socket was closed from other side
                        return b''
                    self._rx_buffer.extend(b)
                    msg_start = self._rx_buffer.find(self.MSG_START_TOKEN)
                    if msg_start != -1:
                        break
                self._rx_buffer = self._rx_buffer[msg_start:]  # Remove msg start token from buffer

                while len(self._rx_buffer) < self.MSG_HEADER_LEN:
                    b = self._socket.recv(self.RX_CHUNK_SIZE)
                    if b == b'':  # If socket was closed from other side
                        return b''
                    self._rx_buffer.extend(b)
                msg_len = int.from_bytes(self._rx_buffer[self.MSG_START_TOKEN_LEN:self.MSG_START_TOKEN_LEN + self.MSG_SIZE_HINT_LEN], "big")
                self._rx_buffer = self._rx_buffer[self.MSG_HEADER_LEN:]  # Remove msg header from buffer

                # Receive actual message
                while len(self._rx_buffer) < msg_len:
                    b = self._socket.recv(self.RX_CHUNK_SIZE)
                    if b == b'':  # If socket was closed from other side
                        return b''
                    self._rx_buffer.extend(b)
                msg = self._rx_buffer[:msg_len]
                self._rx_buffer = self._rx_buffer[msg_len:]  # Remove received message from buffer

                if len(self._rx_buffer) > self.ALLOWED_RX_BUFFERBLOAT:
                    warnings.warn(f"Bufferbloat is very large which means that incoming messages aren't processed fast enough. "
                                  f"After message receive {len(self._rx_buffer)} bytes were left over in the buffer.", RuntimeWarning)
                return bytes(msg)
            return b''
        else:
            raise self.NotConnectedError("Cannot receive when device is not connected via Bluetooth!")

    def deserialize(self, received: bytes):
        try:
            new_data: dict[str, any] = json.loads(received.decode())
        except ValueError:
            raise self.InvalidDataError(f"Could not interprete received data: {received}")
        else:
            self._rx_data.update(new_data)  # Update rx data interface. This simultaneously verifies that the data is consistent with the interface.

    @staticmethod
    def discover():
        nearby_devices = discover_devices(duration=5, lookup_names=True)
        print(f"Found {len(nearby_devices)} devices:")
        for addr, name in nearby_devices:
            print(f"Adress: {addr} - Name: {name}")
