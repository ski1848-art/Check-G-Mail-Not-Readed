import os
import json
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv
from app.utils.logger import get_logger

load_dotenv()

logger = get_logger("config")

def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")

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
    INTERNAL_AUTH_TOKEN: str = os.environ.get("INTERNAL_AUTH_TOKEN", "")
    
    # Firestore / Routing
    ROUTING_SOURCE: str = os.environ.get("ROUTING_SOURCE", "firestore") # firestore | json
    FIRESTORE_PROJECT_ID: str = os.environ.get("FIRESTORE_PROJECT_ID", "")
    ROUTING_CACHE_TTL_SEC: int = int(os.environ.get("ROUTING_CACHE_TTL_SEC", "60"))
    LEARNING_ENABLED: bool = os.environ.get("LEARNING_ENABLED", "true").lower() == "true"

    # Feature Flags (default OFF)
    FEATURE_SLACK_SIGNATURE_VERIFY: bool = _env_bool("FEATURE_SLACK_SIGNATURE_VERIFY", False)
    FEATURE_REQUIRE_INTERNAL_TOKEN: bool = _env_bool("FEATURE_REQUIRE_INTERNAL_TOKEN", False)
    FEATURE_ENFORCE_LIMITS_DURING_BATCH: bool = _env_bool("FEATURE_ENFORCE_LIMITS_DURING_BATCH", False)
    FEATURE_USAGE_INCREMENT_ON_SNAPSHOT_FAILURE: bool = _env_bool("FEATURE_USAGE_INCREMENT_ON_SNAPSHOT_FAILURE", False)
    FEATURE_GMAIL_PAGINATION: bool = _env_bool("FEATURE_GMAIL_PAGINATION", False)

    # CORS
    CORS_ALLOWED_ORIGINS: str = os.environ.get("CORS_ALLOWED_ORIGINS", "*")

    # Gmail fetch tuning (only used when related feature flag is ON)
    GMAIL_QUERY_LOOKBACK_DAYS: int = int(os.environ.get("GMAIL_QUERY_LOOKBACK_DAYS", "1"))
    GMAIL_MAX_RESULTS_PER_USER: int = int(os.environ.get("GMAIL_MAX_RESULTS_PER_USER", "50"))
    GMAIL_MAX_PAGES_PER_USER: int = int(os.environ.get("GMAIL_MAX_PAGES_PER_USER", "1"))

    # LLM pricing (USD per 1M tokens)
    LLM_PRICE_INPUT_PER_1M: float = float(os.environ.get("LLM_PRICE_INPUT_PER_1M", "0.80"))
    LLM_PRICE_OUTPUT_PER_1M: float = float(os.environ.get("LLM_PRICE_OUTPUT_PER_1M", "4.00"))
    LLM_PRICE_CACHE_READ_PER_1M: float = float(os.environ.get("LLM_PRICE_CACHE_READ_PER_1M", "0.08"))
    LLM_PRICE_CACHE_WRITE_PER_1M: float = float(os.environ.get("LLM_PRICE_CACHE_WRITE_PER_1M", "1.00"))
    
    # Configuration Paths
    BASE_DIR = Path(__file__).parent.parent  # /app/config.py -> /
    ROUTING_CONFIG_PATH = BASE_DIR / "config" / "routing_rules.json"
    SPAM_FILTER_CONFIG_PATH = BASE_DIR / "config" / "spam_filter.json"
    
    # Defaults
    SCORE_THRESHOLD_NOTIFY = 0.50
    
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
        # LLM_API_KEY는 레거시 (현재 AWS Bedrock 사용). 별도 경고 불필요.
        if not cls.AWS_ACCESS_KEY_ID or not cls.AWS_SECRET_ACCESS_KEY:
            logger.warning("AWS credentials are missing. Bedrock LLM calls will fail.")
        if cls.FEATURE_SLACK_SIGNATURE_VERIFY and not cls.SLACK_SIGNING_SECRET:
            logger.warning("FEATURE_SLACK_SIGNATURE_VERIFY is enabled but SLACK_SIGNING_SECRET is missing.")
        if cls.FEATURE_REQUIRE_INTERNAL_TOKEN and not cls.INTERNAL_AUTH_TOKEN:
            logger.warning("FEATURE_REQUIRE_INTERNAL_TOKEN is enabled but INTERNAL_AUTH_TOKEN is missing.")
