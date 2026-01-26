import json
import logging
import sys

# Configure structured logging for Cloud Run
def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '{"severity": "%(levelname)s", "message": "%(message)s", "component": "%(name)s"}'
    )
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = [handler]
    
    # Set third-party loggers to WARNING to reduce noise
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

