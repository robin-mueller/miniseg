from pathlib import Path
from PySide6.QtCore import QObject, Property
from PySide6.QtQml import qmlRegisterSingletonType


class Parameters(QObject):
    @Property(int)
    def refresh_rate_hz(self):
        return 10

    @Property(str)
    def default_recording_dir(self):
        return str(Path.cwd() / "recording")
    

class Theme(QObject):
    @Property(str, constant=True)
    def foreground(self):
        return "#e4e7eb"
    
    @Property(str, constant=True)
    def background(self):
        return "#202124"

    @Property(str, constant=True)
    def border(self):
        return "#3f4042"

    @Property(str, constant=True)
    def primary(self):
        return "#8ab4f7"
    
    
# noinspection PyTypeChecker
qmlRegisterSingletonType(Parameters, "Configuration", 1, 0, "Parameters")
# noinspection PyTypeChecker
qmlRegisterSingletonType(Theme, "Configuration", 1, 0, "Theme")

PARAMETERS = Parameters()
THEME = Theme()


