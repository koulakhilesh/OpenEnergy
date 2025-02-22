import logging


class Logger:
    """
    A custom logger class that provides logging functionality with different log levels.

    Attributes:
        DEBUG (int): Log level for debug messages.
        INFO (int): Log level for informational messages.
        WARNING (int): Log level for warning messages.
        ERROR (int): Log level for error messages.
        CRITICAL (int): Log level for critical messages.

    Methods:
        __init__(self, level=INFO): Initializes the logger with the specified log level.
        debug(self, msg): Logs a debug message.
        info(self, msg): Logs an informational message.
        warning(self, msg): Logs a warning message.
        error(self, msg): Logs an error message.
        critical(self, msg): Logs a critical message.
    """

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

    def __init__(self, level=INFO):
        """
        Initializes the logger with the specified log level.

        Args:
            level (int): The log level to set. Defaults to INFO.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(level)

        if not self.logger.handlers:
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)

            self.logger.addHandler(handler)

    def debug(self, msg):
        """
        Logs a debug message.

        Args:
            msg (str): The message to log.
        """
        self.logger.debug(msg)

    def info(self, msg):
        """
        Logs an informational message.

        Args:
            msg (str): The message to log.
        """
        self.logger.info(msg)

    def warning(self, msg):
        """
        Logs a warning message.

        Args:
            msg (str): The message to log.
        """
        self.logger.warning(msg)

    def error(self, msg):
        """
        Logs an error message.

        Args:
            msg (str): The message to log.
        """
        self.logger.error(msg)

    def critical(self, msg):
        """
        Logs a critical message.

        Args:
            msg (str): The message to log.
        """
        self.logger.critical(msg)
