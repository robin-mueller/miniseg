from pathlib import Path
from PySide6.QtCore import QObject, Property
from PySide6.QtQml import qmlRegisterSingletonType

HC06_BLUETOOTH_ADDRESS = "98:D3:A1:FD:34:63"
JSON_INTERFACE_DEFINITION_PATH = Path(__file__).parent.parent / "interface.json"
DEFAULT_RECORDING_DIR = Path(__file__).parent.parent / "recording"
PARAMETERS_DIR = Path(__file__).parent.parent / "data" / "parameters"


class Parameters(QObject):
    @Property(int)
    def refresh_rate_hz(self):
        return 40


class Theme(QObject):
    @Property(str, constant=True)
    def foreground(self):
        return "#e4e7eb"

    @Property(str, constant=True)
    def dark_foreground(self):
        return "#b9c1Cb"

    @Property(str, constant=True)
    def background(self):
        return "#181e25"

    @Property(str, constant=True)
    def border(self):
        return "#505153"

#    @QMLProperty(str, constant=True)
#    def secondary(self):
#        return "#ffe2c2"

    @Property(str, constant=True)
    def primary(self):
        return "#6ec4c4"


# noinspection PyTypeChecker
qmlRegisterSingletonType(Parameters, "Configuration", 1, 0, "Parameters")
# noinspection PyTypeChecker
qmlRegisterSingletonType(Theme, "Configuration", 1, 0, "Theme")

PARAMETERS = Parameters()
THEME = Theme()
