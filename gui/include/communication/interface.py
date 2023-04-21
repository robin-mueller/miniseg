import re
import json

from functools import reduce
from pathlib import Path
from threading import RLock
from collections import UserDict
from include.plotting import StampedData


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
    def to_device(self):
        return self.json_dict[self.TO_DEVICE_KEY]

    @property
    def from_device(self):
        return self.json_dict[self.FROM_DEVICE_KEY]


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

    def __init__(self, interface_json: dict[str, str | dict], *add_members: tuple[str, type], **kwargs):
        if not isinstance(interface_json, dict):
            raise TypeError(f"Wrong type of interface_json: {type(interface_json)}. "
                            f"The interface must be defined as an arbitrarily nested dict with string values that specify the data type.")
        super().__init__(interface_json, **kwargs)

        # Add optional additional members
        self.update({name: t for name, t in add_members})

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
    It can be arbitrarily nested and its values refer to a particular timestamp.
    """

    # This specifies the cases where conversion from set_type to defined_type is explicitly allowed when __setitem__ is called.
    # A single or multiple types may be specified inside a list.
    # Format {set_type: list[defined_type(s)])
    # Example: Let's say I set interface["foo"] = 0, but "foo" is defined as float. If I want to allow conversion to float from int I add {int: [..., float, ...]} to the whitelist.
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

    def __init__(self, interface_definition: InterfaceDefinition):
        super().__init__()
        self._access_lock = RLock()
        self._interface_def: UserDict[str, type | InterfaceDefinition] = interface_definition

        for key, val in self._interface_def.items():
            if isinstance(val, InterfaceDefinition):
                self.data[key] = Interface(val)
            elif isinstance(val, type):
                self.data[key] = StampedData(val(), 0)  # Initialize by default value
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

    def __setitem__(self, key: str | tuple, value: StampedData | tuple | dict):
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

                if isinstance(value, tuple) and not isinstance(value, StampedData):
                    value = StampedData(*value)  # Overwrite value here with a StampedData instance

                if not isinstance(value, StampedData):
                    raise ValueError(f"Setting a value requires the value to be an instance of {StampedData}!")

                defined_type = self._interface_def[key]
                set_type = type(value.value)
                if set_type != defined_type and defined_type not in self._CONVERSION_WHITELIST.get(set_type, []):
                    raise self.ConversionError(f"Type of {value.value=} is {type(value.value)} but defined was {defined_type}. "
                                               f"Interface values must be loyal to their types defined at initialization.")
                try:
                    converted_val = defined_type(value.value)
                except ValueError:
                    raise self.ConversionError(f"Could no convert {value.value=} of type {type(value.value)} for key '{key}' to {self._interface_def[key]}.")
                else:
                    super().__setitem__(key, StampedData(converted_val, value.timestamp))
                    return

            elif isinstance(key, tuple):  # If dict is accessed using multiple keys
                d = self.__getitem__(key[:-1])
                if isinstance(d, Interface):
                    d[key[-1]] = value
                    return
                raise TypeError(f"Key {key[-2]} doesn't point to another instance of {type(self)}.")

            raise TypeError(f"Argument 'key' must be a string or a tuple of strings not {type(key)}.")
