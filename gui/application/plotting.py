import numpy as np
import seaborn as sns
import pyqtgraph as pg
import configuration as config

from .communication.interface import StampedData
from typing import Callable
from dataclasses import dataclass
from collections import UserDict
from time import perf_counter
from PySide6.QtCore import QTimer


@dataclass(frozen=True, eq=True)
class CurveDefinition:
    """
    Class for creating monitoring curve definitions.

    - label: Name of the curve.
    - get_func: Getter function of the respective value.
    """
    label: str
    value_getter: Callable[[], StampedData]  # Has to return a tuple of value and timestamp in this order


@dataclass
class ColouredCurve:
    """
    Helper class to define an initial color together with the curve.

    - definition: CurveDefinition instance.
    - color: Pen color of the curve represented by one of b, g, r, c, m, y, k, w or other types specified here: https://pyqtgraph.readthedocs.io/en/latest/user_guide/style.html#line-fill-and-color.
             If None, color is chosen automatically.
    """
    definition: CurveDefinition
    color: any = None


class CurveLibrary:
    _DEFS: dict[str, CurveDefinition] = {}

    @staticmethod
    def colorize(curves: set[CurveDefinition]) -> dict[CurveDefinition, str]:
        color_palette = sns.color_palette('husl', len(curves)).as_hex()
        return {curve: color_palette[index] for index, curve in enumerate(curves)}

    @classmethod
    def add_definition(cls, key: str, curve_definition: CurveDefinition):
        cls._DEFS[key] = curve_definition

    @classmethod
    def definitions(cls, key: str = None, color: any = None):
        if key is None:
            return cls._DEFS
        if color is None:
            return cls._DEFS[key]
        return ColouredCurve(cls._DEFS[key], color)


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
    def __init__(self, label: str, color: any, window_size_sec: float):
        """
        A pyqtgraph PlotDataItem that scrolls the x axis when its data is being updated.

        :param label: The label of the curve.
        :param color: The color of the curve. Accepts everything that pg.mkPen accepts for color keyword.
        :param window_size_sec: The length of the plotted curve in seconds.
        """
        super().__init__(name=label, pen=pg.mkPen(color=color, width=1))
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

    def append_data(self, value: float | None, ts: float, *, display=True):
        """
        Updates the curve of the plot by appending a new value at the provided frame timestamp ts.
        The initially defined window size in seconds will be respected.

        :param value: Value to append to the curve.
        :param ts: Timestamp of the value that indicates the time elapsed since the start of the application.
        :param display: Only updates the display if set to True. Otherwise, just stores the data.
        """
        # Initialize timeseries if first time calling
        _value = np.nan if value is None else value
        if not self._visible_timeseries.any():
            t = np.linspace(ts - self._window_duration, ts, round(self._window_duration * config.PARAMETERS.refresh_rate_hz))  # Initial time axis which is subject to change
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

    def __init__(self, curves: list[ColouredCurve] = None, *, title: str = None, xlabel: str = 'Time elapsed in s', ylabel: str = None, window_size_sec: float = 30, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.showGrid(y=True)
        self.addLegend(offset=(1, 1))
        self.setMouseEnabled(x=False)
        self.setLabel('left', ylabel, color=config.THEME.foreground)
        self.setLabel('bottom', xlabel)
        self._window_size = window_size_sec

        # Add data to plot
        self._curves_dict: dict[CurveDefinition, TimeseriesCurve] = {}
        if curves:
            for curve in curves:
                self.add_curve(curve)

        self.timer = QTimer()
        # noinspection PyUnresolvedReferences
        self.timer.timeout.connect(self._update)

    def add_curve(self, curve: ColouredCurve):
        _curve = TimeseriesCurve(curve.definition.label, curve.color, self._window_size)
        self._curves_dict[curve.definition] = _curve
        self.addItem(_curve)

    def remove_curve(self, curve_definition: CurveDefinition):
        self.removeItem(self._curves_dict[curve_definition])
        del self._curves_dict[curve_definition]

    @property
    def title(self):
        return self.titleLabel.text

    @title.setter
    def title(self, text: str):
        self.setTitle(text, color=config.THEME.foreground, size='18px')

    @property
    def curves_dict(self):
        return self._curves_dict

    def _update(self):
        for curve_def, time_curve in self._curves_dict.items():
            time_curve.append_data(*curve_def.value_getter())

    def start(self, interval_hz: int = config.PARAMETERS.refresh_rate_hz):
        self.timer.start(round(1000 / interval_hz))


class GraphDict(UserDict):
    def __init__(self, graphics_layout_widget: pg.GraphicsLayoutWidget, dictionary=None, /, **kwargs):
        super().__init__(dictionary, **kwargs)
        self._layout = graphics_layout_widget.ci

    def __setitem__(self, key: int, item: MonitoringGraph):
        assert isinstance(key, int), TypeError("Keys have to be strings!")
        assert isinstance(item, MonitoringGraph), TypeError("Items have to be instances of MonitoringGraph!")

        # Remove old graph
        if key in self.keys():
            self._remove_graph_from_layout(key)

        # Assign item to dict
        super().__setitem__(key, item)

        # Add new graph to position of old graph
        self._layout.addItem(item, row=key, col=1)

    def __delitem__(self, key: int):
        self._remove_graph_from_layout(key)
        super().__delitem__(key)

    def _remove_graph_from_layout(self, key: int):
        self._layout.removeItem(self.data[key])
