"""Logging utilities (migrated from root logger.py)."""
import logging
import sys
from pathlib import Path
from typing import Optional

def setup_logger(
	name: str = "lightrag",
	level: str = "INFO",
	log_file: Optional[str] = None,
	log_format: Optional[str] = None
) -> logging.Logger:
	logger = logging.getLogger(name)
	logger.setLevel(getattr(logging, level.upper()))
	for handler in logger.handlers[:]:
		logger.removeHandler(handler)
	if log_format is None:
		log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
	formatter = logging.Formatter(log_format)
	console_handler = logging.StreamHandler(sys.stdout)
	console_handler.setFormatter(formatter)
	logger.addHandler(console_handler)
	if log_file:
		try:
			log_path = Path(log_file)
			log_path.parent.mkdir(parents=True, exist_ok=True)
			file_handler = logging.FileHandler(log_file)
			file_handler.setFormatter(formatter)
			logger.addHandler(file_handler)
			logger.info(f"Logging to file: {log_file}")
		except Exception as e:  # noqa: BLE001
			logger.warning(f"Could not set up file logging: {e}")
	return logger

def get_logger(name: str = "lightrag") -> logging.Logger:
	return logging.getLogger(name)

class PerformanceLogger:
	def __init__(self, logger: Optional[logging.Logger] = None):
		self.logger = logger or get_logger("performance")
		self.metrics = {}
	def start_timer(self, operation: str):
		from datetime import datetime as _dt
		self.metrics[operation] = {'start': _dt.now(), 'end': None, 'duration': None}
	def end_timer(self, operation: str):
		from datetime import datetime as _dt
		if operation in self.metrics:
			self.metrics[operation]['end'] = _dt.now()
			duration = self.metrics[operation]['end'] - self.metrics[operation]['start']
			self.metrics[operation]['duration'] = duration
			self.logger.info(f"{operation} completed in {duration.total_seconds():.2f} seconds")
	def log_metric(self, name: str, value: float, unit: str = ""):
		self.logger.info(f"{name}: {value}{unit}")
	def get_summary(self) -> dict:
		summary = {}
		for op, data in self.metrics.items():
			if data['duration']:
				summary[op] = data['duration'].total_seconds()
		return summary

performance_logger = PerformanceLogger()

def log_function_call(func_name: str):
	def decorator(func):
		import asyncio
		if asyncio.iscoroutinefunction(func):
			async def async_wrapper(*args, **kwargs):
				performance_logger.start_timer(func_name)
				try:
					result = await func(*args, **kwargs)
					performance_logger.end_timer(func_name)
					return result
				except Exception as e:  # noqa: BLE001
					performance_logger.end_timer(func_name)
					raise e
			return async_wrapper
		else:
			def sync_wrapper(*args, **kwargs):
				performance_logger.start_timer(func_name)
				try:
					result = func(*args, **kwargs)
					performance_logger.end_timer(func_name)
					return result
				except Exception as e:  # noqa: BLE001
					performance_logger.end_timer(func_name)
					raise e
			return sync_wrapper
	return decorator

