import pandas as pd
import configuration as config

from tools.visualization import TimeSeriesPlot
from pathlib import Path

FIGURE_EXPORT_DIR = Path(__file__).parent.parent.parent / "images"


def main():
    record_file = config.DEFAULT_RECORDING_DIR / "position.csv"
    df = pd.read_csv(record_file, header=[0, 1, 2], index_col=0)
    df.sort_index(axis=1, inplace=True)

    data = {
        "Position in mm": [
            ("Measurement", df["Graph 5", "observer/position/z_mm"]),
            ("FF Model", df["Graph 5", "ff_model/position/z_mm"]),
            ("Setpoint", df["Graph 5", "pos_setpoint_mm"]),
        ],
        "Tilt velocity in rad/s": [
            ("Measurement", df["Graph 1", "observer/tilt/vel_rad_s"]),
            ("FF Model", df["Graph 1", "ff_model/tilt/vel_rad_s"]),
        ],
        "Wheel speed in rad/s": [
            ("Measurement", df["Graph 3", "observer/wheel/vel_rad_s"]),
            ("FF Model", df["Graph 3", "ff_model/wheel/vel_rad_s"]),
        ]
    }

    plot = TimeSeriesPlot("Position", **data)
    plot.figure.show()

    if not FIGURE_EXPORT_DIR.exists():
        FIGURE_EXPORT_DIR.mkdir()
    plot.figure.savefig(FIGURE_EXPORT_DIR / (record_file.stem + ".pdf"))


if __name__ == '__main__':
    main()
