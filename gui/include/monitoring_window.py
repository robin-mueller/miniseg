import inspect
import pandas as pd

from typing import Optional
from pathlib import Path
from configuration import PARAMETERS
from include.helper import MonitoringGraph, GraphDict, KeepMenuOpen
from include.curve_definition import CurveLibrary, CurveDefinition
from resources.monitoring_window_ui import Ui_MonitoringWindow
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMenu, QFileDialog
from PySide6.QtCore import Qt, QTime


class MonitoringWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.recording_start: Optional[QTime] = None
        self.keep_menu_open_filter = KeepMenuOpen(self)

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.ui = Ui_MonitoringWindow()
        self.ui.setupUi(self)
        self.ui.graph_layout.setBackground(None)
        self.ui.menuGraphs.installEventFilter(self.keep_menu_open_filter)
        self.ui.actionAddGraph.triggered.connect(self.add_graph)
        self.ui.actionStartRecording.triggered.connect(self.start_recording)
        self.ui.actionStopRecording.triggered.connect(self.stop_recording)
        
        self.graphs: GraphDict[int, MonitoringGraph] = GraphDict(self.ui.graph_layout)
    
    def add_graph(self):
        graph_id = 0
        while graph_id in self.graphs:
            graph_id += 1
        graph_title = f"Graph {graph_id + 1}"
        graph_menu = QMenu(graph_title)
        self.ui.menuGraphs.insertMenu(self.ui.menuGraphs.actions()[graph_id + 1], graph_menu)
        graph_menu.installEventFilter(self.keep_menu_open_filter)
        remove_action = graph_menu.addAction("Remove")
        graph_menu.addSection("Curves")
        curve_actions: dict[str, QAction] = {name: graph_menu.addAction(name) for name, t in inspect.get_annotations(CurveLibrary).items() if t == CurveDefinition}
        
        def create_graph():
            curves = [CurveLibrary.__getattribute__(CurveLibrary, name) for name, action in curve_actions.items() if action.isChecked()]
            self.graphs[graph_id] = MonitoringGraph(curves, graph_title)
            self.graphs[graph_id].start()
            
        def delete_graph():
            graph_menu.deleteLater()
            del self.graphs[graph_id]
            
        remove_action.triggered.connect(delete_graph)
        for action in curve_actions.values():
            action.setCheckable(True)
            action.triggered.connect(create_graph)
        
        create_graph()
        
    def start_recording(self):
        if any([graph.curve_dict for graph in self.graphs.values()]):  # Only start recording if any curves have been defined
            for graph in self.graphs.values():
                for curve in graph.curve_dict.values():
                    curve.recording = True
            self.ui.actionStartRecording.setEnabled(False)
            self.ui.actionStopRecording.setEnabled(True)
            self.recording_start = QTime.currentTime()

    def stop_recording(self):
        for graph in self.graphs.values():
            for curve in graph.curve_dict.values():
                curve.recording = False
        self.ui.actionStartRecording.setEnabled(True)
        self.ui.actionStopRecording.setEnabled(False)

        # Save recording
        rec_dir = Path(PARAMETERS.default_recording_dir)
        if not rec_dir.exists():
            rec_dir.mkdir()
        path, _ = QFileDialog.getSaveFileName(self, "Save Monitoring Data", str(rec_dir), "CSV (*.csv)")

        df = []
        for graph in self.graphs.values():
            for curve_def, curve in graph.curve_dict.items():
                df.append(pd.DataFrame(curve.recording_array.T, columns=pd.MultiIndex.from_product([[graph.title], [curve_def.label], ['Time', 'Value']])))
        df = pd.concat(df, axis=1)

        if path != '':
            if Path(path).suffix != '.csv':
                path += '.csv'
            df.to_csv(path)
