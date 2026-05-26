import logging
import logging.config

from app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    level_name = settings.log_level.upper()
    level = logging.getLevelName(level_name)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {settings.log_level}")

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": level_name,
            },
        }
    )
