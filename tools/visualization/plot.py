import pandas as pd
import matplotlib.pyplot as plt


class TimeSeriesPlot:
    def __init__(self, title: str = None, **data: list[tuple[str, pd.DataFrame]]):
        self._fig, self._ax = plt.subplots(len(data), 1, sharex='all')
        for index, (label, timeseries) in enumerate(data.items()):
            for name, df in timeseries:
                self._ax[index].plot(df.iloc[:, 0] - df.iloc[:, 0].min(), df.iloc[:, 1], label=name)
            self._ax[index].set_ylabel(label)
            self._ax[index].legend()
        self._fig.supxlabel("Time in seconds")
        if title:
            self._fig.suptitle(title)

    @property
    def figure(self) -> plt.Figure:
        return self._fig
