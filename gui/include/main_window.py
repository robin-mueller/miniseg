from gui.include.bt_remote import BTRemote
from gui.resources.main_window_ui import Ui_MainWindow
from gui.include.helper import MonitoringGraph, GraphDict
from gui.include.curve_definition import CurveDefinition, CurveLibrary
from gui.include.monitoring_window import MonitoringWindow
from gui.include.widget import SetpointSlider, ParameterSection
from PySide6.QtCore import Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QProgressBar, QLabel


# noinspection PyPropertyAccess
class MiniSegGUI(QMainWindow):
    def __init__(self):
        self.monitors: list[MonitoringWindow] = []
        self.bt_remote = BTRemote("98:D3:A1:FD:34:63")
        
        self.bt_connect_progress_bar = QProgressBar()
        self.bt_connect_progress_bar.setMaximumSize(250, 15)
        self.bt_connect_progress_bar.setRange(0, 0)
        self.bt_connect_label = QLabel("Connecting ...")
        
        super().__init__(None)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.plot_overview.setBackground(None)
        self.ui.actionNewMonitor.triggered.connect(self.on_open_monitor)
        self.ui.actionConnect.triggered.connect(self.on_bluetooth_connect)
        self.ui.actionDisconnect.triggered.connect(self.on_bluetooth_disconnect)
        
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
    
    @Slot()
    def on_bluetooth_connect(self):
        self.ui.actionConnect.setEnabled(False)
        self.ui.statusbar.addWidget(self.bt_connect_label)
        self.ui.statusbar.addWidget(self.bt_connect_progress_bar)
        self.bt_connect_label.show()
        self.bt_connect_progress_bar.show()
        self.bt_remote.async_connect(self.on_bluetooth_connected, self.on_bluetooth_connection_failed)
    
    @Slot()
    def on_bluetooth_connected(self):
        self.ui.statusbar.removeWidget(self.bt_connect_label)
        self.ui.statusbar.removeWidget(self.bt_connect_progress_bar)
        self.ui.statusbar.showMessage("Connection successful!", 3000)
        self.ui.actionDisconnect.setEnabled(True)
    
    @Slot(str)
    def on_bluetooth_connection_failed(self, exception_name: str):
        self.ui.statusbar.removeWidget(self.bt_connect_label)
        self.ui.statusbar.removeWidget(self.bt_connect_progress_bar)
        self.ui.actionConnect.setEnabled(True)
        self.ui.statusbar.showMessage(f"Connecting failed - {exception_name} occured!", 3000)
    
    @Slot()
    def on_bluetooth_disconnect(self):
        self.bt_remote.disconnect()
        self.ui.actionConnect.setEnabled(True)
        self.ui.actionDisconnect.setEnabled(False)
        self.ui.statusbar.showMessage("Disconnected from device!", 3000)
    
    @Slot()
    def on_open_monitor(self):
        new_monitor = MonitoringWindow()
        new_monitor.destroyed.connect(lambda: self.monitors.remove(new_monitor))
        self.monitors.append(new_monitor)
        new_monitor.show()
    
    def closeEvent(self, event: QCloseEvent):
        for monitor in self.monitors:
            monitor.close()
        self.bt_remote.disconnect()
        super().closeEvent(event)
        