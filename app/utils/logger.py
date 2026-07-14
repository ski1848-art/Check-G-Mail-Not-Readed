"""
logger.py - Cloud Run 환경용 구조화 로깅

[로그 형식]
  JSON 구조: {"severity": "INFO", "message": "...", "component": "main"}
  Cloud Run에서 자동으로 Cloud Logging에 수집됨.

[사용법]
  from app.utils.logger import get_logger
  logger = get_logger("my_module")
  logger.info("처리 완료")
"""
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

