import itertools
import pandas as pd
import configuration as config

from functools import partial
from collections import UserDict
from typing import Optional
from pathlib import Path
from .helper import KeepMenuOpen
from .plotting import MonitoringGraph, GraphDict, CurveLibrary, CurveDefinition, ColouredCurve
from resources.monitoring_window_ui import Ui_MonitoringWindow
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QFileDialog
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

        self.graphs: UserDict[int, MonitoringGraph] = GraphDict(self.ui.graph_layout)
        self.add_graph()

    def update_curve_colors(self):
        curves: set[CurveDefinition] = set(itertools.chain(*[graph.curves_dict.keys() for graph in self.graphs.values()]))
        colors = CurveLibrary.colorize(curves)
        for graph in self.graphs.values():
            for curve_definition, curve in graph.curves_dict.items():
                curve.setPen(colors[curve_definition])

    def add_graph(self):
        graph_id = 0
        while graph_id in self.graphs:
            graph_id += 1
        graph_title = f"Graph {graph_id + 1}"
        graph_menu = self.ui.menuGraphs.addMenu(graph_title)
        graph_menu.installEventFilter(self.keep_menu_open_filter)
        remove_action = graph_menu.addAction("Remove")
        graph_menu.addSection("Curves")
        curve_actions: dict[str, QAction] = {name: graph_menu.addAction(name) for name in CurveLibrary.definitions()}

        def toggle_curve(curve_definition: CurveDefinition, show: bool):
            if show:
                self.graphs[graph_id].add_curve(ColouredCurve(curve_definition))
            else:
                self.graphs[graph_id].remove_curve(curve_definition)
            self.update_curve_colors()

        def delete_graph():
            graph_menu.deleteLater()
            del self.graphs[graph_id]
            self.update_curve_colors()

        remove_action.triggered.connect(delete_graph)
        for name, action in curve_actions.items():
            action.setCheckable(True)
            action.toggled.connect(partial(toggle_curve, CurveLibrary.definitions(name)))

        self.graphs[graph_id] = MonitoringGraph(title=graph_title)
        self.graphs[graph_id].start()

    def start_recording(self):
        if any([graph.curves_dict for graph in self.graphs.values()]):  # Only start recording if any curves have been defined
            for graph in self.graphs.values():
                for curve in graph.curves_dict.values():
                    curve.recording = True
            self.ui.actionStartRecording.setEnabled(False)
            self.ui.actionStopRecording.setEnabled(True)
            self.recording_start = QTime.currentTime()

    def stop_recording(self):
        for graph in self.graphs.values():
            for curve in graph.curves_dict.values():
                curve.recording = False
        self.ui.actionStartRecording.setEnabled(True)
        self.ui.actionStopRecording.setEnabled(False)

        # Save recording
        rec_dir = config.DEFAULT_RECORDING_DIR
        if not rec_dir.exists():
            rec_dir.mkdir()
        path, _ = QFileDialog.getSaveFileName(self, "Save Monitoring Data", str(rec_dir), "CSV (*.csv)")
        if path:
            df = []
            for graph in self.graphs.values():
                for curve_def, curve in graph.curves_dict.items():
                    df.append(pd.DataFrame(curve.recording_array.T, columns=pd.MultiIndex.from_product([[graph.title], [curve_def.label], ['Time', 'Value']])))
            df = pd.concat(df, axis=1)

            if Path(path).suffix != '.csv':
                path += '.csv'
            df.to_csv(path)
