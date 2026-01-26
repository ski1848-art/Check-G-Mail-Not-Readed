import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from google.cloud import firestore
from app.config import Config
from app.utils.logger import get_logger

logger = get_logger("settings_store")

# 시스템 제어 관련 상수
SYSTEM_CONTROL_COLLECTION = "system_control"
SYSTEM_CONTROL_DOC = "status"
DAILY_USAGE_COLLECTION = "daily_usage"

class SettingsStore:
    """
    Manages global system settings from Firestore with TTL caching.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SettingsStore, cls).__new__(cls)
                    cls._instance._init_store()
        return cls._instance

    def _init_store(self):
        self.db = None
        if Config.FIRESTORE_PROJECT_ID:
            try:
                import google.auth
                import os
                
                # Cloud Run 환경에서 Secret Manager를 통한 JSON 주입 대응
                creds_backup = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
                if creds_backup and creds_backup.startswith('{'):
                    del os.environ['GOOGLE_APPLICATION_CREDENTIALS']
                
                credentials, project = google.auth.default()
                self.db = firestore.Client(project=Config.FIRESTORE_PROJECT_ID, credentials=credentials)
                
                if creds_backup:
                    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_backup
            except Exception as e:
                logger.error(f"Failed to initialize Firestore client in SettingsStore: {e}")
        
        self.settings: Dict[str, Any] = {}
        self.last_updated = 0
        self.cache_ttl = 300  # 설정값은 조금 더 길게 캐시 (5분)

    def get_setting(self, key: str, default: Any = None) -> Any:
        self._refresh_if_needed()
        return self.settings.get(key, default)

    def get_all_settings(self) -> Dict[str, Any]:
        self._refresh_if_needed()
        return self.settings

    def _refresh_if_needed(self):
        now = time.time()
        if now - self.last_updated > self.cache_ttl:
            with self._lock:
                if now - self.last_updated > self.cache_ttl:
                    self._load_from_firestore()
                    self.last_updated = time.time()

    def _load_from_firestore(self):
        if not self.db:
            return

        try:
            logger.info("Refreshing system settings from Firestore...")
            doc = self.db.collection("system_settings").document("general").get()
            if doc.exists:
                self.settings = doc.to_dict()
                logger.info("System settings loaded successfully.")
            else:
                logger.warning("System settings document not found in Firestore. Using defaults.")
        except Exception as e:
            logger.error(f"Error loading system settings from Firestore: {e}")

    # =============================================
    # 시스템 제어 기능 (긴급 중지/재시작)
    # =============================================
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        시스템 상태 조회.
        Returns: {
            "enabled": bool,
            "paused_at": str or None,
            "paused_by": str or None,
            "pause_reason": str or None,
            "daily_limit_calls": int,
            "daily_limit_cost_usd": float,
        }
        """
        if not self.db:
            return {"enabled": True, "daily_limit_calls": 1000, "daily_limit_cost_usd": 5.0}
        
        try:
            doc = self.db.collection(SYSTEM_CONTROL_COLLECTION).document(SYSTEM_CONTROL_DOC).get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    "enabled": data.get("enabled", True),
                    "paused_at": data.get("paused_at"),
                    "paused_by": data.get("paused_by"),
                    "pause_reason": data.get("pause_reason"),
                    "daily_limit_calls": data.get("daily_limit_calls", 1000),
                    "daily_limit_cost_usd": data.get("daily_limit_cost_usd", 5.0),
                    "last_batch_at": data.get("last_batch_at"),
                    "last_batch_processed": data.get("last_batch_processed", 0),
                }
            return {"enabled": True, "daily_limit_calls": 1000, "daily_limit_cost_usd": 5.0}
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {"enabled": True, "daily_limit_calls": 1000, "daily_limit_cost_usd": 5.0}
    
    def set_system_enabled(self, enabled: bool, user: str = "system", reason: str = None) -> bool:
        """
        시스템 활성화/비활성화 설정.
        """
        if not self.db:
            logger.warning("Firestore not available. Cannot change system status.")
            return False
        
        try:
            data = {
                "enabled": enabled,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": user,
            }
            
            if not enabled:
                data["paused_at"] = datetime.now(timezone.utc).isoformat()
                data["paused_by"] = user
                data["pause_reason"] = reason or "수동 일시 중지"
            else:
                data["paused_at"] = None
                data["paused_by"] = None
                data["pause_reason"] = None
            
            self.db.collection(SYSTEM_CONTROL_COLLECTION).document(SYSTEM_CONTROL_DOC).set(data, merge=True)
            logger.info(f"System {'enabled' if enabled else 'disabled'} by {user}. Reason: {reason}")
            return True
        except Exception as e:
            logger.error(f"Error setting system status: {e}")
            return False
    
    def update_last_batch_info(self, processed_count: int):
        """배치 실행 정보 업데이트"""
        if not self.db:
            return
        
        try:
            self.db.collection(SYSTEM_CONTROL_COLLECTION).document(SYSTEM_CONTROL_DOC).set({
                "last_batch_at": datetime.now(timezone.utc).isoformat(),
                "last_batch_processed": processed_count,
            }, merge=True)
        except Exception as e:
            logger.error(f"Error updating last batch info: {e}")
    
    def set_daily_limits(self, limit_calls: int = None, limit_cost_usd: float = None) -> bool:
        """일일 한도 설정"""
        if not self.db:
            return False
        
        try:
            data = {}
            if limit_calls is not None:
                data["daily_limit_calls"] = limit_calls
            if limit_cost_usd is not None:
                data["daily_limit_cost_usd"] = limit_cost_usd
            
            if data:
                data["updated_at"] = datetime.now(timezone.utc).isoformat()
                self.db.collection(SYSTEM_CONTROL_COLLECTION).document(SYSTEM_CONTROL_DOC).set(data, merge=True)
            return True
        except Exception as e:
            logger.error(f"Error setting daily limits: {e}")
            return False

    # =============================================
    # 일일 사용량 추적
    # =============================================
    
    def _get_today_key(self) -> str:
        """오늘 날짜 키 (KST 기준)"""
        from datetime import timedelta
        kst = timezone(timedelta(hours=9))
        return datetime.now(kst).strftime("%Y-%m-%d")
    
    def get_daily_usage(self) -> Dict[str, Any]:
        """
        오늘의 사용량 조회.
        Returns: {"calls": int, "cost_usd": float}
        """
        if not self.db:
            return {"calls": 0, "cost_usd": 0.0}
        
        try:
            today = self._get_today_key()
            doc = self.db.collection(DAILY_USAGE_COLLECTION).document(today).get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    "date": today,
                    "calls": data.get("calls", 0),
                    "cost_usd": data.get("cost_usd", 0.0),
                    "input_tokens": data.get("input_tokens", 0),
                    "output_tokens": data.get("output_tokens", 0),
                }
            return {"date": today, "calls": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
        except Exception as e:
            logger.error(f"Error getting daily usage: {e}")
            return {"date": self._get_today_key(), "calls": 0, "cost_usd": 0.0}
    
    def increment_daily_usage(self, calls: int = 1, cost_usd: float = 0.0, 
                              input_tokens: int = 0, output_tokens: int = 0) -> bool:
        """일일 사용량 증가"""
        if not self.db:
            return False
        
        try:
            today = self._get_today_key()
            doc_ref = self.db.collection(DAILY_USAGE_COLLECTION).document(today)
            
            # Firestore increment 사용
            doc_ref.set({
                "calls": firestore.Increment(calls),
                "cost_usd": firestore.Increment(cost_usd),
                "input_tokens": firestore.Increment(input_tokens),
                "output_tokens": firestore.Increment(output_tokens),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, merge=True)
            return True
        except Exception as e:
            logger.error(f"Error incrementing daily usage: {e}")
            return False
    
    def check_daily_limit_exceeded(self) -> Tuple[bool, str]:
        """
        일일 한도 초과 여부 체크.
        Returns: (exceeded: bool, reason: str)
        """
        status = self.get_system_status()
        usage = self.get_daily_usage()
        
        limit_calls = status.get("daily_limit_calls", 1000)
        limit_cost = status.get("daily_limit_cost_usd", 5.0)
        
        current_calls = usage.get("calls", 0)
        current_cost = usage.get("cost_usd", 0.0)
        
        if current_calls >= limit_calls:
            return True, f"일일 호출 한도 초과 ({current_calls}/{limit_calls})"
        
        if current_cost >= limit_cost:
            return True, f"일일 비용 한도 초과 (${current_cost:.2f}/${limit_cost:.2f})"
        
        return False, ""
    
    def is_system_enabled(self) -> Tuple[bool, str]:
        """
        시스템 실행 가능 여부 체크 (활성화 상태 + 한도 체크).
        Returns: (enabled: bool, reason: str)
        """
        status = self.get_system_status()
        
        # 1. 수동 중지 상태 체크
        if not status.get("enabled", True):
            reason = status.get("pause_reason", "수동 일시 중지됨")
            return False, reason
        
        # 2. 일일 한도 체크
        exceeded, reason = self.check_daily_limit_exceeded()
        if exceeded:
            return False, reason
        
        return True, "정상"

