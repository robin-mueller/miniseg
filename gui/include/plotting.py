import numpy as np
import seaborn as sns
import pyqtgraph as pg

from typing import Callable
from dataclasses import dataclass
from collections import UserDict
from configuration import THEME, PARAMETERS
from time import perf_counter
from PySide6.QtCore import QTime, QTimer


@dataclass(frozen=True)
class CurveDefinition:
    """
    Class for creating monitoring curve definitions

    - label: Name of the curve.
    - get_func: Getter function of the respective value.
    - color: Pen color of the curve represented by one of b, g, r, c, m, y, k, w or other types specified here: https://pyqtgraph.readthedocs.io/en/latest/user_guide/style.html#line-fill-and-color.
             If None, color gets chosen automatically
    """
    label: str
    get_func: Callable[[], float]
    color: any = None


CURVE_LIBRARY: dict[str, CurveDefinition] = {}


class ScheduledValue:
    def __init__(self, interval_sec: float, start_value: float = 0, initial_previous_value: float = None):
        """
        This introduces a schedule for a value. This means, that a value is only updated,
        when the specified time interval since the last schedule update is exceeded.

        :param interval_sec: Frequency to update the value schedules in seconds.
        :param start_value: Specifies the start value, which is returned by the request method until the first schedule has been initiated.
        :param initial_previous_value: Specifies the value that will be returned by accessing property previous_value before first schedule has timeouted.
        """
        self.interval_sec = interval_sec
        self._last_schedule_update = perf_counter()
        self._value = start_value
        self._prev_val = start_value if initial_previous_value is None else initial_previous_value
        self._register_arr = np.array([self._value])

    @property
    def previous_value(self):
        return self._prev_val

    @property
    def schedule_timeout(self):
        """
        Check whether the value's schedule timeout has been reached. This means, that a new value will be returned upon request.

        :return: True if timout is reached, False otherwise.
        """
        return perf_counter() - self._last_schedule_update > self.interval_sec

    def register(self, value: float):
        """
        Registers a new value in the array.

        :param value: The new value to register.
        """
        self._register_arr = np.append(self._register_arr, [value])

    def request(self, value: float = None):
        """
        Returns the average of all registered values if the last value update lies
        sufficiently long in the past.

        :param value: Optional. This is a shorthand for registering and requesting a value at the same time. The given value will be registered before the request is issued.
        :return: The value of the current schedule.
        """
        if value is not None:
            self.register(value)

        if self.schedule_timeout:
            self._prev_val = self._value
            self._value = np.mean(self._register_arr)
            self._register_arr = np.array([])
            self._last_schedule_update = perf_counter()
        return self._value


class TimeseriesCurve(pg.PlotDataItem):
    def __init__(self, curve_definition: CurveDefinition, window_size_sec: float, color_hex: str):
        """
        A pyqtgraph PlotDataItem that scrolls the x axis when its data is being updated.

        :param curve_definition: A set of definition parameters.
        :param window_size_sec: The length of the plotted curve in seconds.
        :param color_hex: A HEX code specifiying the curve color.
        """
        super().__init__(name=curve_definition.label, pen=pg.mkPen(color=color_hex, width=1))
        self._window_duration = window_size_sec
        self._visible_timeseries = np.array([[], []])
        self._recording_active = False
        self._recording_arr = np.array([[], []])  # Store the entire data received inside an extra array

    @property
    def recording(self):
        return self._recording_active

    @recording.setter
    def recording(self, val: bool):
        if val:
            self._recording_arr = np.array([[], []])  # Reset recording array
        self._recording_active = val

    @property
    def recording_array(self):
        return self._recording_arr

    def append_data(self, ts: float, value: float | None, *, display=True):
        """
        Updates the curve of the plot by appending a new value at the provided frame timestamp ts.
        The initially defined window size in seconds will be respected.

        :param ts: Timestamp of the value that indicates the time elapsed since the start of the application.
        :param value: Value to append to the curve.
        :param display: Only updates the display if set to True. Otherwise, just stores the data.
        """
        # Initialize timeseries if first time calling
        _value = np.nan if value is None else value
        if not self._visible_timeseries.any():
            t = np.linspace(ts - self._window_duration, ts, round(self._window_duration * PARAMETERS.refresh_rate_hz))  # Initial time axis which is subject to change
            self._visible_timeseries = np.array([t, np.full(t.shape[0], np.nan)])  # Initial values np.nan

        # Extend recording array
        if self._recording_active:
            self._recording_arr = np.append(self._recording_arr, [[ts], [_value]], axis=1)

        # Extend the timeseries data of the curve
        self._visible_timeseries = np.append(self._visible_timeseries, [[ts], [_value]], axis=1)
        while self._visible_timeseries[0, -1] - self._visible_timeseries[0, 0] > self._window_duration:
            self._visible_timeseries = np.delete(self._visible_timeseries, 0, axis=1)
        if display:
            self.setData(self._visible_timeseries[0], self._visible_timeseries[1])


class MonitoringGraph(pg.PlotItem):
    """
    Class for defining real-time monitoring graphs.
    """
    earliest_start = QTime.currentTime()

    def __init__(self, curves: list[CurveDefinition], title: str, *, xlabel: str = 'Time elapsed in s', ylabel: str = None, window_size_sec: float = 30, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.showGrid(y=True)
        self.addLegend(offset=(1, 1))
        self.setMouseEnabled(x=False)
        self.setLabel('left', ylabel, color=THEME.foreground)
        self.setLabel('bottom', xlabel)

        # Add data to plot
        color_palette = sns.color_palette('husl', len(curves)).as_hex()
        self._graph_curves: dict[CurveDefinition, TimeseriesCurve] = {
            curve_def: TimeseriesCurve(curve_def, window_size_sec, color_palette[index] if curve_def.color is None else curve_def.color)
            for index, curve_def in enumerate(curves)
        }
        for curve in self._graph_curves.values():
            self.addItem(curve)

        self.timer = QTimer()
        # noinspection PyUnresolvedReferences
        self.timer.timeout.connect(self._update)

    @property
    def title(self):
        return self.titleLabel.text

    @title.setter
    def title(self, text: str):
        self.setTitle(text, color=THEME.foreground, size='18px')

    @property
    def curve_dict(self):
        return self._graph_curves

    def _update(self):
        for curve_def, data in self._graph_curves.items():
            data.append_data(MonitoringGraph.earliest_start.msecsTo(QTime.currentTime()) / 1000, curve_def.get_func())

    def start(self, interval_hz: int = PARAMETERS.refresh_rate_hz):
        if self._graph_curves:
            current_time = QTime.currentTime()
            if MonitoringGraph.earliest_start > current_time:
                MonitoringGraph.earliest_start = current_time
            self.timer.start(round(1000 / interval_hz))


class GraphDict(UserDict):
    def __init__(self, grpahics_layout: pg.GraphicsLayout, dictionary=None, /, **kwargs):
        super().__init__(dictionary, **kwargs)
        self._layout = grpahics_layout

    def __setitem__(self, key: int, item: MonitoringGraph):
        assert isinstance(key, int), TypeError("Keys have to be strings!")
        assert isinstance(item, MonitoringGraph), TypeError("Items have to be instances of MonitoringGraph!")

        # Remove old graph
        if key in self.keys():
            self._remove_graph_from_layout(key)

        super().__setitem__(key, item)

        # Insert item to layout
        existing_item = self._layout.getItem(row=key, col=1)
        self._layout.addItem(item, row=key, col=1)  # Place item
        while existing_item is not None:
            existing_item = self._layout.getItem(row=key + 1, col=1)  # Copy item that occupies the slot for existing_item
            self._layout.addItem(existing_item, row=key + 1, col=1)  # Place existing_item

    def __delitem__(self, key: int):
        self._remove_graph_from_layout(key)
        super().__delitem__(key)

    def _remove_graph_from_layout(self, key: int):
        self._layout.removeItem(self.data[key])
