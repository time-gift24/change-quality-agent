import logging

import pytest

from app.core.config import Settings
from app.core.logging import configure_logging


def test_configure_logging_sets_root_level() -> None:
    configure_logging(Settings(log_level="DEBUG"))

    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_rejects_invalid_level() -> None:
    with pytest.raises(ValueError, match="Invalid log level"):
        configure_logging(Settings(log_level="NOPE"))


def test_configure_logging_keeps_existing_library_loggers_enabled() -> None:
    configure_logging(Settings(log_level="INFO"))

    assert logging.getLogger("uvicorn.error").disabled is False
