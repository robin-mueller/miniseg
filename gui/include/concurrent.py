from typing import Callable
from PySide6.QtCore import QTimer, QObject, Signal, QThread


class _ConcurrentWorker(QObject):
    trigger = Signal()
    success = Signal(object)
    failed = Signal(Exception)
    finished = Signal()

    def __init__(self, do_work: Callable[[], object]):
        super().__init__()
        self._do_work = do_work
        self.trigger.connect(self.run)

    def run(self):
        try:
            ret = self._do_work()
        except Exception as e:
            self.failed.emit(e)
        else:
            self.success.emit(ret)
        finally:
            self.finished.emit()


class ConcurrentTask:
    """
    A persistent handle (meaning the object doesn't have to be reinstantiated every time the task is supposed to start again)
    for a concurrent task using QThread which is defined by the constructor arguments.
    The approach used is based on the guide from https://realpython.com/python-pyqt-qthread/
    """
    class WorkFailedError(Exception):
        def __init__(self, c: Callable, exception: Exception):
            super().__init__(f"No exception handler was connected but an exception occured during execution of callable '{c.__name__}': \n{exception.__class__.__name__}: {str(exception)}")

    def __init__(self, do_work: Callable[[], any], *, on_success: Callable[[any], None] = None, on_failed: Callable[[Exception], None] = None, repeat_ms: int = None):

        def create_worker():
            worker = _ConcurrentWorker(do_work)
            if on_success:
                worker.success.connect(on_success)
            if on_failed:
                worker.failed.connect(on_failed)
            else:
                def raise_ex(exception: Exception):
                    raise self.WorkFailedError(do_work, exception)
                worker.failed.connect(raise_ex)
            return worker

        self.create_worker = create_worker
        self.worker: _ConcurrentWorker | None = None
        self.thread: QThread | None = None
        self.timer = QTimer()  # TODO: Remove timer and implement timing inside worker while loop!
        if repeat_ms is None:
            self.timer.setSingleShot(True)
        else:
            self.timer.setInterval(repeat_ms)
        self.timer.timeout.connect(lambda: self.worker.trigger.emit())

    def start(self):
        if not self.thread:
            self.worker = self.create_worker()
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.timer.start)
            self.thread.finished.connect(self.worker.deleteLater)
            self.thread.finished.connect(self.thread.deleteLater)
            if self.timer.isSingleShot():
                self.worker.finished.connect(self.stop)
            self.thread.start()
        else:
            raise RuntimeError("This task is already running!")

    def stop(self):
        """
        If the task is not done yet, this method stops the task and
        blocks the calling thread until the worker has finished.
        """
        if self.thread:
            self.timer.stop()
            self.thread.quit()
            self.thread.wait()
            self.worker = None
            self.thread = None
