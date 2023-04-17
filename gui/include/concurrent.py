from abc import abstractmethod, ABCMeta
from types import NoneType
from typing import Callable
from PySide6.QtCore import QTimer, QObject, Signal, QThread


class _ConcurrentWorker(QObject):
    """
    This class provides the structure for concurrent workers but only subclasses allowed.
    They have to be defined manually because each concurrent worker needs its own signals. They would otherwise be shared.
    """
    success = Signal(object)
    failed = Signal(Exception)
    finished = Signal()

    def __init__(self, do_work: Callable[[], object]):
        super().__init__()
        self._do_work = do_work

    def __new__(cls, *args, **kwargs):
        if cls is _ConcurrentWorker:
            raise TypeError(f"Only children of '{cls.__name__}' may be instantiated!")
        return super().__new__(cls, *args, **kwargs)

    @property
    def work_handle(self):
        return self._do_work

    def run(self):
        try:
            ret = self._do_work()
        except Exception as e:
            self.failed.emit(e)
        else:
            self.success.emit(ret)
        finally:
            self.finished.emit()


class BTConnectWorker(_ConcurrentWorker):
    success = Signal(NoneType)
    failed = Signal(Exception)
    finished = Signal()


class BTReceiveWorker(_ConcurrentWorker):
    success = Signal(bytes)
    failed = Signal(Exception)
    finished = Signal()


class ConcurrentTask:
    """
    A persistent handle (meaning the object doesn't have to be reinstantiated every time the task is supposed to start again)
    for a concurrent task using QThread which is defined by the constructor arguments.
    The approach used is based on the guide from https://realpython.com/python-pyqt-qthread/ and http://blog.debao.me/2013/08/how-to-use-qthread-in-the-right-way-part-1/.
    """
    class WorkFailedError(Exception):
        def __init__(self, c: Callable, exception: Exception):
            super().__init__(f"No exception handler was connected but an exception occured during execution of callable '{c.__name__}': \n{exception.__class__.__name__}: {str(exception)}")

    def __init__(self, worker: _ConcurrentWorker, *, on_success: Callable[[any], None] = None, on_failed: Callable[[Exception], None] = None, repeat_ms: int = None):

        def create_worker():
            if on_success:
                worker.success.connect(on_success)
            if on_failed:
                worker.failed.connect(on_failed)
            else:
                def raise_ex(exception: Exception):
                    raise self.WorkFailedError(worker.work_handle, exception)
                worker.failed.connect(raise_ex)
            return worker

        def create_timer():
            timer = QTimer()
            if repeat_ms is None:
                timer.setSingleShot(True)
            else:
                timer.setInterval(repeat_ms)
            return timer

        self.create_worker = create_worker
        self.create_timer = create_timer
        self.thread: QThread | None = None

        # References that have to be kept alive for the task to work
        self._worker = None
        self._timer = None

    def start(self):
        """
        Creates the worker thread and starts the task execution.
        """
        if not self.thread:
            self._worker = self.create_worker()
            self._timer = self.create_timer()
            self.thread = QThread()
            self._worker.moveToThread(self.thread)
            self._timer.moveToThread(self.thread)  # Let timer execute in subthread to reduce signal clutter in main thread when using quick intervals
            self._timer.timeout.connect(self._worker.run)
            if self._timer.isSingleShot():
                self._worker.finished.connect(self.stop)
            self.thread.started.connect(self._timer.start)
            self.thread.start()
        else:
            raise RuntimeError("This task is already running!")

    def stop(self):
        """
        If the task is not done yet, this method stops the task and
        blocks the calling thread until the worker has finished.
        """
        if self.thread:
            self.thread.quit()
            self.thread.wait()
            self.thread = None
            self._worker = None
            self._timer = None
