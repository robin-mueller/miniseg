import re
import json

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from collections import UserDict
from typing import Callable, TypeVar


class ConversionError(Exception):
    pass


class UnmatchedKeyError(Exception):
    def __init__(self, key: str, available_keys: list | dict | UserDict):
        super().__init__(f"Key '{key}' has no match with the specified interface keys {list(available_keys)}.")


class SetItemNotAllowedError(Exception):
    def __init__(self, key: str):
        super().__init__(
            f"Key '{key}' doesn't point to a value, but rather to a nested instance of {DataInterface}. "
            f"Calling __setitem__() is only allowed for a key on the lowest level, hence only for keys that point to values. "
            f"Otherwise protected {DataInterface.__name__} objects would be overwritten!")


class JsonInterfaceReader:
    TO_DEVICE_KEY = "TO_DEVICE"
    FROM_DEVICE_KEY = "FROM_DEVICE"

    def __init__(self, file_path: Path):
        # Verify that json interface file is valid
        with file_path.open() as interface_file:
            self.json_dict = json.load(interface_file)
            if not all([base_key in self.json_dict for base_key in [self.TO_DEVICE_KEY, self.FROM_DEVICE_KEY]]):
                raise KeyError(f"Base key(s) not found! Specifiers for the data interface to and from the device "
                               f"have to be exactly {self.TO_DEVICE_KEY} and {self.FROM_DEVICE_KEY} respectively. "
                               f"Found {self.json_dict.keys()} instead.")

    @property
    def to_device(self) -> dict[str, str | dict]:
        return self.json_dict[self.TO_DEVICE_KEY]

    @property
    def from_device(self) -> dict[str, str | dict]:
        return self.json_dict[self.FROM_DEVICE_KEY]


DataInterfaceDefinitionType = TypeVar('DataInterfaceDefinitionType')


class DataInterfaceDefinition(UserDict):
    # Maps the types that are allowed to be specified in the interface json file to Python types
    TYPE_TRANSLATION = {
        "char[]": str,
        "bool": bool,
        "float": float,
        "double": float,
        "int": int,
        "int8_t": int,
        "int16_t": int,
        "int32_t": int,
        "int64_t": int,
        "uint8_t": int,
        "uint16_t": int,
        "uint32_t": int,
        "uint64_t": int,
    }

    class MissingCorrespondingType(Exception):
        pass

    def __init__(self, *members: tuple[str, type], **kw_members):
        super().__init__({name: t for name, t in members}, **kw_members)

    def __getitem__(self: DataInterfaceDefinitionType, key: str | tuple) -> DataInterfaceDefinitionType:
        if isinstance(key, str):  # If dict is accessed using a single key
            try:
                return super().__getitem__(key)
            except KeyError:
                raise UnmatchedKeyError(key, self) from None
        elif isinstance(key, tuple):  # If dict is accessed using multiple keys
            if len(key) > 1:
                return self.__getitem__(key[0]).__getitem__(key[1:])
            return self.__getitem__(key[0])
        else:
            raise TypeError(f"Argument 'key' must be a string or a tuple of strings not {type(key)}.")

    def __setitem__(self, key: str, value):
        if isinstance(key, str):  # If dict is accessed using a single key
            if isinstance(value, str):
                if value not in self.TYPE_TRANSLATION:
                    raise self.MissingCorrespondingType(f"Type translation for '{value}' is missing.")
                super().__setitem__(key, self.TYPE_TRANSLATION[re.sub(r'\[\d+]', '[]', value)])  # Replace arry size specification with just empty []
                return
            if isinstance(value, dict):
                super().__setitem__(key, self.__class__(**value))
                return
            if isinstance(value, type):
                super().__setitem__(key, value)
                return

            raise TypeError(f"val must be a type, string or dict but provided was {type(value)}.")

        if isinstance(key, tuple):  # If dict is accessed using multiple keys
            d = self.__getitem__(key[:-1])
            if isinstance(d, type(self)):
                d[key[-1]] = value
                return
            raise TypeError(f"Key {key[-2]} doesn't point to another instance of {type(self)}.")

        raise TypeError(f"Argument 'key' must be a string or a tuple of strings not {type(key)}.")


@dataclass(frozen=True, eq=True)
class StampedData:
    value: any
    timestamp: float


DataInterfaceType = TypeVar('DataInterfaceType')


class DataInterface(UserDict):
    """
    A thread safe dict-like object that acts like a runtime validated buffer for incoming and outgoing data.
    It can be arbitrarily nested and its values refer to a particular timestamp.
    """

    # This specifies the cases where conversion from set_type to defined_type is explicitly allowed when __setitem__ is called.
    # A single or multiple types may be specified inside a list.
    # Format: {set_type: list[defined_type(s)]).
    # Example: Let's say I set interface["foo"] = 0, but "foo" is defined as float. If I want to allow conversion to float from int I add {int: [..., float, ...]} to the whitelist.
    CONVERSION_WHITELIST = {
        int: [float, bool],
        float: [int]
    }

    class JSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, DataInterface):
                return obj.data
            if isinstance(obj, StampedData):
                return obj.value
            return super().default(obj)

    def __init__(self, interface_definition: DataInterfaceDefinition, stamper: Callable[[], float]):
        """
        Defines the interface.

        :param interface_definition: Instance of InterfaceDefinition.
        :param stamper: A function or method to be called everytime a value is set. This is used to get the timestamp of the set operation.
        """
        super().__init__()
        self._access_lock = RLock()
        self._interface_def: UserDict[str, type | DataInterfaceDefinition] = interface_definition
        self._stamper = stamper
        self._setitem_callbacks: dict[str, Callable[[StampedData], None]] = {}

        for key, val in self._interface_def.items():
            if isinstance(val, DataInterfaceDefinition):
                self.data[key] = DataInterface(val, stamper)
            elif isinstance(val, type):
                self.data[key] = StampedData(val(), 0)  # Initialize by default value
            else:
                raise TypeError(f"Wrong value type: {type(val)}! Only InterfaceDefinition and types allowed.")

    @property
    def definition(self):
        return self._interface_def

    def execute_when_set(self, key: str, callback: Callable[[StampedData], None]):
        if key in self.keys():
            self._setitem_callbacks[key] = callback
        else:
            raise UnmatchedKeyError(key, self)

    def __getitem__(self: DataInterfaceType, key: str | tuple) -> StampedData | DataInterfaceType:
        """
        Get an item of the data interface.

        :param key: When accessing a single member, the key must be str. If the member is nested key must be tuple of str.
        """
        with self._access_lock:
            if isinstance(key, str):  # If dict is accessed using a single key
                try:
                    return super().__getitem__(key)
                except KeyError:
                    raise UnmatchedKeyError(key, self) from None
            elif isinstance(key, tuple):  # If dict is accessed using multiple keys
                if len(key) > 1:
                    return self.__getitem__(key[0]).__getitem__(key[1:])
                return self.__getitem__(key[0])
            else:
                raise TypeError(f"Argument 'key' must be a string or a tuple of strings not {type(key)}.")

    def __setitem__(self, key: str | tuple, value):
        """
        Set an item of the data interface.

        :param key: When accessing a single member, the key must be str. If the member is nested key must be tuple of str.
        :param value: If multiple values are to be set value must be a dict of all values to be set. A value can be of any type.
        If value is not already a StampedData instance or a dict of those, a timestamp will be inferred using the stamper callable provided when constructed.
        """
        with self._access_lock:
            if isinstance(key, str):  # If dict is accessed using a single key
                if key not in self.keys():
                    raise UnmatchedKeyError(key, self)
                if isinstance(self.__getitem__(key), DataInterface):
                    if isinstance(value, dict):
                        # Parse dict and try to assign values recursively
                        for k, v in value.items():
                            self.__getitem__(key).__setitem__(k, v)
                        return
                    else:
                        raise SetItemNotAllowedError(key)

                if not isinstance(value, StampedData):
                    value = StampedData(value, self._stamper())  # Add timestamp if not already given

                defined_type = self._interface_def[key]
                set_type = type(value.value)
                if set_type != defined_type and defined_type not in self.CONVERSION_WHITELIST.get(set_type, []):
                    raise ConversionError(f"Type of object {value.value} is {type(value.value)} but defined was {defined_type}. "
                                          f"Interface values must be loyal to their types defined at initialization.")
                try:
                    converted_val = defined_type(value.value)
                except ValueError:
                    raise ConversionError(f"Could no convert {value.value=} of type {type(value.value)} for key '{key}' to {self._interface_def[key]}.")
                else:
                    super().__setitem__(key, StampedData(converted_val, value.timestamp))
                    if key in self._setitem_callbacks.keys():
                        self._setitem_callbacks[key](value)
                    return

            elif isinstance(key, tuple):  # If dict is accessed using multiple keys
                d = self.__getitem__(key[:-1])
                if isinstance(d, type(self)):
                    d[key[-1]] = value
                    return
                raise TypeError(f"Key {key[-2]} doesn't point to another instance of {type(self)}.")

            raise TypeError(f"Argument 'key' must be a string or a tuple of strings not {type(key)}.")
