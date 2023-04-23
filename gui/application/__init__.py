import time

PROGRAM_START_TIMESTAMP = time.perf_counter()


def program_uptime():
    return time.perf_counter() - PROGRAM_START_TIMESTAMP
