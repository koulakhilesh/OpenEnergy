import logging
import os
import sys
from io import StringIO

import pytest

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)
from scripts.shared import Logger


@pytest.fixture
def logger():
    log_output = StringIO()
    logger = Logger(level=logging.DEBUG)
    handler = logging.StreamHandler(log_output)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.logger.addHandler(handler)
    return logger, log_output


def test_logger(logger):
    logger, log_output = logger
    logger.debug("debug")
    logger.info("info")
    logger.warning("warning")
    logger.error("error")
    logger.critical("critical")

    log_output.seek(0)
    logs = log_output.read().splitlines()

    assert "debug" in logs[0]
    assert "info" in logs[1]
    assert "warning" in logs[2]
    assert "error" in logs[3]
    assert "critical" in logs[4]


if __name__ == "__main__":
    pytest.main([__file__])
