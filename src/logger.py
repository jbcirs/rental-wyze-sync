import logging
import logging.config
import os

default_log_level = 'INFO'
log_level = os.getenv('LOGGING_LEVEL')

if not log_level:
	log_level = default_log_level

logging.config.dictConfig(
		{"version": 1, "disable_existing_loggers": True,	
		"formatters": {"json": {"()": "json_log_formatter.JSONFormatter"},},
		"handlers": {"console": {"formatter": "json", "class": "logging.StreamHandler",}},
		"loggers": {"": {"handlers": ["console"], "level": f"{log_level}"},},}
		)

class Logger():
	logger = None

	def __init__(self):
		self.logger = logging

	def error(self, msg):
		self.logger.error(msg)

	def warn(self, msg):
		self.logger.warn(msg)

	def warning(self, msg):
		self.logger.warn(msg)

	def info(self, msg):
		self.logger.info(msg)

	def debug(self, msg):
		self.logger.debug(msg)