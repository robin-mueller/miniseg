from gui.include.bt_remote import BTRemote
from gui.resources.main_window_ui import Ui_MainWindow
from gui.include.helper import MonitoringGraph, GraphDict
from gui.include.curve_definition import CurveDefinition, CurveLibrary
from gui.include.monitoring_window import MonitoringWindow
from gui.include.widget import SetpointSlider, ParameterSection
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow


# noinspection PyPropertyAccess
class MiniSegGUI(QMainWindow):
    def __init__(self):
        self.monitors: list[MonitoringWindow] = []
        self.bt_remote = BTRemote("98:D3:A1:FD:34:63")
        
        super().__init__(None)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.plot_overview.setBackground(None)
        self.ui.actionNewMonitor.triggered.connect(self.open_monitor)
        self.ui.actionConnect.triggered.connect(self.bluetooth_connect)
        self.ui.actionDisconnect.triggered.connect(self.bluetooth_disconnect)
        
        self.parameter_section = ParameterSection(self.ui.parameter_frame)
        self.setpoint_slider = SetpointSlider(self.ui.setpoint_slider_frame)
        CurveLibrary.POSITION_SETPOINT = CurveDefinition("Position Setpoint", lambda: self.setpoint_slider.value)
        
        # Add graphs
        self.graphs: GraphDict[str, MonitoringGraph] = GraphDict(self.ui.plot_overview)
        self.graphs[0] = MonitoringGraph(
            curves=[CurveLibrary.POSITION_SETPOINT],
            title="Position [cm]"
        )
        self.graphs[0].start()
        
    def bluetooth_connect(self):
        try:
            self.ui.statusbar.showMessage("Connecting ...", 3000)
            self.bt_remote.connect()
            self.ui.actionConnect.setEnabled(False)
            self.ui.actionDisconnect.setEnabled(True)
        except Exception as e:
            self.ui.statusbar.showMessage(f"Connecting failed - {type(e).__name__} occured!", 3000)
            
    def bluetooth_disconnect(self):
        self.bt_remote.disconnect()
        self.ui.actionConnect.setEnabled(True)
        self.ui.actionDisconnect.setEnabled(False)
    
    def open_monitor(self):
        new_monitor = MonitoringWindow()
        new_monitor.destroyed.connect(lambda: self.monitors.remove(new_monitor))
        self.monitors.append(new_monitor)
        new_monitor.show()
    
    def closeEvent(self, event: QCloseEvent):
        for monitor in self.monitors:
            monitor.close()
        super().closeEvent(event)
        