"""
config.py - 애플리케이션 설정 로더

환경변수(.env)와 JSON 설정 파일(config/)을 통합 관리.
Firestore의 동적 설정(system_settings)과 함께 사용됨.

[주요 설정 항목]
- Slack Bot 토큰/시크릿
- AWS Bedrock (AI 모델) 인증 정보
- Google 서비스 계정 (Gmail API, Firestore)
- 라우팅 소스 (firestore | json)
- 알림 임계값 (score_threshold_notify)
- AI 비용 절감 / 사용량 급증 재발방지 (LLM_SUMMARY_BODY_MAX_CHARS,
  USAGE_SPIKE_MULTIPLIER, USAGE_SPIKE_MIN_CALLS, MONTHLY_LIMIT_COST_USD)
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv
from app.utils.logger import get_logger

load_dotenv()

logger = get_logger("config")

class Config:
    """
    Application Configuration Loader.
    Loads environment variables and JSON config files.
    """
    
    # Environment Variables
    SLACK_BOT_TOKEN: str = os.environ.get("SLACK_BOT_TOKEN", "")
    SLACK_SIGNING_SECRET: str = os.environ.get("SLACK_SIGNING_SECRET", "")
    LLM_API_KEY: str = os.environ.get("LLM_API_KEY", "")
    GOOGLE_APPLICATION_CREDENTIALS: str = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    ADMIN_EMAIL: str = os.environ.get("ADMIN_EMAIL", "ski1848@hotseller.co.kr")  # Workspace admin for domain-wide delegation
    AWS_ACCESS_KEY_ID: str = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")
    BEDROCK_MODEL_ID: str = os.environ.get("BEDROCK_MODEL_ID", "arn:aws:bedrock:us-east-1:210506716773:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0")
    # Token-Watcher v2 (LLM 프록시 게이트웨이)
    TOKEN_WATCHER_URL: str = os.environ.get("TOKEN_WATCHER_URL", "")
    TOKEN_WATCHER_KEY: str = os.environ.get("TOKEN_WATCHER_KEY", "")
    # 내부 API 인증 키 (Cloud Run 공개 시 /run-batch 등 보호)
    INTERNAL_API_KEY: str = os.environ.get("INTERNAL_API_KEY", "")
    
    # Firestore / Routing
    ROUTING_SOURCE: str = os.environ.get("ROUTING_SOURCE", "firestore") # firestore | json
    FIRESTORE_PROJECT_ID: str = os.environ.get("FIRESTORE_PROJECT_ID", "")
    ROUTING_CACHE_TTL_SEC: int = int(os.environ.get("ROUTING_CACHE_TTL_SEC", "60"))
    LEARNING_ENABLED: bool = os.environ.get("LEARNING_ENABLED", "true").lower() == "true"
    
    # Configuration Paths
    BASE_DIR = Path(__file__).parent.parent  # /app/config.py -> /
    ROUTING_CONFIG_PATH = BASE_DIR / "config" / "routing_rules.json"
    SPAM_FILTER_CONFIG_PATH = BASE_DIR / "config" / "spam_filter.json"
    
    # Defaults
    SCORE_THRESHOLD_NOTIFY = 0.50

    # ── AI 비용 절감 / 재발 방지 설정 ───────────────────────────────
    # 요약(summary) 생성 시 LLM에 전달할 본문 최대 글자 수.
    # 중요도 '판단'에는 본문을 넣지 않고(비용 절감), 알림 대상(NOTIFY) 요약에만 본문 사용.
    LLM_SUMMARY_BODY_MAX_CHARS: int = int(os.environ.get("LLM_SUMMARY_BODY_MAX_CHARS", "1000"))
    # 최근 평균 대비 이 배수 이상으로 오늘 총비용/통당 비용이 뛰면 '급증'으로 판정하여 알림
    USAGE_SPIKE_MULTIPLIER: float = float(os.environ.get("USAGE_SPIKE_MULTIPLIER", "3.0"))
    # 급증 판정을 위한 오늘의 최소 표본(LLM 처리 건수) — 표본이 적으면 오탐 방지 위해 판정 보류
    USAGE_SPIKE_MIN_CALLS: int = int(os.environ.get("USAGE_SPIKE_MIN_CALLS", "20"))
    # 월 비용 상한(USD) — 초과 시 배치 자동 중단. Firestore system_control에서 재정의 가능
    MONTHLY_LIMIT_COST_USD: float = float(os.environ.get("MONTHLY_LIMIT_COST_USD", "30.0"))
    
    @classmethod
    def load_routing_rules(cls) -> List[Dict[str, Any]]:
        """Load email routing rules from JSON."""
        return cls._load_json_config(cls.ROUTING_CONFIG_PATH, [])

    @classmethod
    def load_spam_filter(cls) -> Dict[str, Any]:
        """Load spam/noise filter rules (blacklists, keywords)."""
        return cls._load_json_config(cls.SPAM_FILTER_CONFIG_PATH, {"blacklist_domains": [], "keywords": []})
    
    @staticmethod
    def _load_json_config(path: Path, default: Any) -> Any:
        try:
            if not path.exists():
                logger.warning(f"Config file not found: {path}. Using default.")
                return default
            
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config {path}: {e}")
            return default

    @classmethod
    def validate(cls):
        """Check if essential configuration is present."""
        if not cls.SLACK_BOT_TOKEN:
            logger.warning("SLACK_BOT_TOKEN is missing. Notification will fail.")
        if not cls.SLACK_SIGNING_SECRET:
            logger.warning("SLACK_SIGNING_SECRET is missing. Slack signature verification will be skipped.")
        if not cls.LLM_API_KEY:
            logger.warning("LLM_API_KEY is missing. AI analysis will be skipped.")
        if not cls.AWS_ACCESS_KEY_ID or not cls.AWS_SECRET_ACCESS_KEY:
            logger.warning("AWS credentials are missing. Bedrock LLM calls will fail.")

