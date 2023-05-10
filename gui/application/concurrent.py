import traceback

from typing import Callable
from PySide6.QtCore import QTimer, QObject, Signal, QThread


class _ConcurrentWorker(QObject):
    """
    This class provides the structure for concurrent workers.
    """
    success = Signal(object)
    failed = Signal(Exception)
    finished = Signal()

    def __init__(self, work_handle: Callable[[], object]):
        super().__init__()
        self._do_work = work_handle

    def run(self):
        try:
            ret = self._do_work()
        except Exception as e:
            self.failed.emit(e)
        else:
            self.success.emit(ret)
        finally:
            self.finished.emit()


class ConcurrentTask(QObject):
    """
    A persistent handle (meaning the object doesn't have to be reinstantiated every time the task is supposed to start again)
    for a concurrent task using QThread which is defined by the constructor arguments.
    The approach used is based on the guide from https://realpython.com/python-pyqt-qthread/ and
    http://blog.debao.me/2013/08/how-to-use-qthread-in-the-right-way-part-1/.
    """
    started = Signal()
    stopped = Signal()

    class WorkFailedError(Exception):
        def __init__(self, c: Callable, exception: Exception):
            super().__init__(f"No exception handler was connected but an exception occured during execution of callable '{c.__name__}': \n{''.join(traceback.format_exception(exception))}")

    def __init__(self, work_handle: Callable[[], object], *, on_success: Callable[[any], None] = None, on_failed: Callable[[Exception], None] = None, repeat_ms: int = None):
        super().__init__()

        def create_worker():
            worker = _ConcurrentWorker(work_handle)
            if on_success:
                worker.success.connect(on_success)
            if on_failed:
                worker.failed.connect(on_failed)
            else:
                def raise_ex(exception: Exception):
                    raise self.WorkFailedError(work_handle, exception)
                worker.failed.connect(raise_ex)
            return worker

        def create_timer():
            timer = QTimer()
            if repeat_ms is None:
                timer.setSingleShot(True)
            else:
                timer.setInterval(repeat_ms)
            return timer

        self._create_worker = create_worker
        self._create_timer = create_timer
        self._thread: QThread | None = None

        # References that have to be kept alive for the task to work
        self._worker: _ConcurrentWorker | None = None
        self._timer: QTimer | None = None

    @property
    def is_active(self):
        return isinstance(self._thread, QThread)

    def start(self):
        """
        Creates the worker thread and starts the task execution.
        """
        if not self.is_active:
            self._worker = self._create_worker()
            self._timer = self._create_timer()
            self._thread = QThread()
            self._worker.moveToThread(self._thread)
            self._timer.moveToThread(self._thread)  # Let timer execute in subthread to reduce signal clutter in main thread when using quick intervals
            self._timer.timeout.connect(self._worker.run)
            if self._timer.isSingleShot():
                self._worker.finished.connect(self.stop)
            self._thread.started.connect(self._timer.start)
            self._thread.finished.connect(self._timer.stop)
            self._thread.start()
            self.started.emit()
        else:
            raise RuntimeError("This task is already running!")

    def stop(self):
        """
        If the task is not done yet, this method stops the task and
        blocks the calling thread until the worker has finished.
        """
        if self.is_active:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
            self._worker = None
            self._timer = None
            self.stopped.emit()
