import logging
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

import structlog

LOG_DIR = Path("../logs")
LOG_FILE_NAME = "../logs"
LOG_LEVEL = logging.DEBUG


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

def set_logging_config():
    # See https://betterstack.com/community/guides/logging/structlog/#final-thoughts
    logging.basicConfig(
        stream=sys.stdout,
        level=LOG_LEVEL,
    )
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,  # If log level is too low, abort pipeline and throw away log entry.
            structlog.processors.EventRenamer("msg"),
            structlog.stdlib.add_log_level,  # Add log level to event dict.
            structlog.processors.TimeStamper(fmt="iso"),  # Add a timestamp in ISO 8601 format.
            structlog.processors.StackInfoRenderer(),  # If the "stack_info" key in the event dict is true, remove it and render the current stack trace in the "stack" key.
            # If the "exc_info" key in the event dict is either true or a sys.exc_info() tuple, remove "exc_info" and render the exception with traceback into the "exception" key.
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),  # If some value is in bytes, decode it to a Unicode str.
            structlog.processors.KeyValueRenderer(key_order=["timestamp", "msg", "context"]),
            structlog.processors.JSONRenderer(),  # Render the final event dict as JSON. or use: structlog.dev.ConsoleRenderer(),
        ],
        # `wrapper_class` is the bound logger that you get back from
        # get_logger(). This one imitates the API of `logging.Logger`.
        wrapper_class=structlog.stdlib.BoundLogger,
        # `logger_factory` is used to create wrapped loggers that are used for OUTPUT. This one returns a `logging.Logger`. The final value (a JSON
        # string) from the final processor (`JSONRenderer`) will be passed to the method of the same name as that you've called on the bound logger.
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


class Logger(metaclass=SingletonMeta):
    def __init__(self, include_log_file: bool = False):

        set_logging_config()
        self._logger: structlog.stdlib.BoundLogger = structlog.get_logger()

        if include_log_file:
            self._create_log_file_handler()

    def _create_stream_handler(self):
        stream_handler = logging.StreamHandler(stream=sys.stdout)
        stream_handler.setLevel(LOG_LEVEL)
        # return stream_handler
        self._logger.addHandler(stream_handler)

    def _create_log_file_handler(self):
        directory = os.path.dirname(os.path.abspath(LOG_DIR))
        if not os.path.exists(directory):
            os.mkdir(directory)
        file_handler = logging.FileHandler(LOG_FILE_NAME, mode="w", encoding="utf-8")
        self._logger.addHandler(file_handler)

    def debug(self, message: str,) -> None:
        self._logger.debug(message)

    def info(self, message: str,) -> None:
        self._logger.info(message)

    def warning(self, message: str,) -> None:
        self._logger.warning(message)

    def error(self, message: str,) -> None:
        self._logger.error(message)

    def critical(self, message: str,) -> None:
        self._logger.critical(message)