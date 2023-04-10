from dataclasses import dataclass
from typing import Callable


class CurveColors:
    BLUE = 'b'
    GREEN = 'g'
    RED = 'r'
    CYAN = 'c'
    MAGENTA = 'm'
    YELLOW = 'y'
    BLACK = 'k'
    WHITE = 'w'
    DEFAULT = BLUE


@dataclass(frozen=True, eq=True)
class CurveDefinition:
    """
    Class for creating monitoring curve definitions

    - label: Name of the curve.
    - get_func: Getter function of the respective value.
    - color: Color of the curve represented by one of b, g, r, c, m, y, k, w.
    - window_sec: Visible time window in seconds.
    """
    label: str
    get_func: Callable[[], float]
    color: str = CurveColors.DEFAULT
    window_sec: float = 30  # The default window size of the scrolling graphs in seconds#


CURVE_LIBRARY: dict[str, CurveDefinition] = {}
    