"""
settings_store.py - 시스템 설정 및 제어 관리

[역할]
  1. 시스템 전역 설정 (system_settings/general): 블랙리스트, 임계값 등
  2. 시스템 제어 (system_control/status): 일시중지/재시작, 일일/월 한도
  3. 일일 사용량 추적 (daily_usage/{YYYY-MM-DD}): AI 호출 횟수, 비용
  4. 월 사용량 추적 (monthly_usage/{YYYY-MM}): 월 누적 AI 호출 횟수, 비용
  5. 사용량 급증 감지 (check_usage_spike): 재발 방지용 이상 징후 판정

[캐시 전략]
  - 싱글톤 패턴 (SettingsStore._instance)
  - 설정값 TTL: 5분 (자주 변경되지 않으므로)

[시스템 제어 흐름]
  관리자 웹 → POST /api/system → Firestore system_control 업데이트
  → 다음 배치 실행 시 is_system_enabled()에서 체크 → 중지/한도초과 시 스킵

[일일 한도 체크]
  - daily_limit_calls: AI 호출 횟수 한도 (기본 1000)
  - daily_limit_cost_usd: 비용 한도 (기본 $5.0)
  - KST 기준 날짜로 일일 사용량 집계

[월 한도 / 사용량 급증 감지 — 재발 방지 장치]
  - check_monthly_limit_exceeded(): monthly_limit_cost_usd(기본 $30.0, Config.
    MONTHLY_LIMIT_COST_USD) 초과 시 is_system_enabled()에서 배치를 스킵
  - check_usage_spike(): 최근 7일 평균 대비 오늘 비용이 급증(기본 3배 이상,
    USAGE_SPIKE_MULTIPLIER)했는지 판정. 총비용뿐 아니라 '통당 비용
    (cost/calls)' 급증도 함께 감지 — 메일 1건당 비용이 오르는 코드/설정
    변경(과거 7배 급증 사례)을 다음 날 즉시 잡아내기 위함
  - 오늘 호출 수가 USAGE_SPIKE_MIN_CALLS 미만이거나 최근 유효 일자가 3일
    미만이면 표본 부족으로 판정을 보류(오탐 방지)
  - 급증/월한도 알림은 spike_alert_sent / cost_alert_sent 플래그로 하루
    중복 전송을 방지
"""
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
MONTHLY_USAGE_COLLECTION = "monthly_usage"
SETTINGS_COLLECTION = "system_settings"
SETTINGS_DOC = "general"

# 비용 알림 기본값
DEFAULT_COST_ALERT_RECIPIENT = "U04E9PMTLTZ"  # 변홍주

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
                    "monthly_limit_cost_usd": data.get("monthly_limit_cost_usd", Config.MONTHLY_LIMIT_COST_USD),
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
                    "cost_alert_sent": data.get("cost_alert_sent", False),
                    "spike_alert_sent": data.get("spike_alert_sent", False),
                }
            return {"date": today, "calls": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "cost_alert_sent": False, "spike_alert_sent": False}
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
            
            # daily + monthly를 원자적 배치로 1커밋 (부분 실패로 인한 집계 불일치 방지)
            now_iso = datetime.now(timezone.utc).isoformat()
            month = today[:7]  # YYYY-MM

            def _usage_payload():
                return {
                    "calls": firestore.Increment(calls),
                    "cost_usd": firestore.Increment(cost_usd),
                    "input_tokens": firestore.Increment(input_tokens),
                    "output_tokens": firestore.Increment(output_tokens),
                    "updated_at": now_iso,
                }

            batch = self.db.batch()
            batch.set(doc_ref, _usage_payload(), merge=True)
            batch.set(self.db.collection(MONTHLY_USAGE_COLLECTION).document(month), _usage_payload(), merge=True)
            batch.commit()
            return True
        except Exception as e:
            logger.error(f"Error incrementing daily usage: {e}")
            return False
    
    def check_daily_limit_exceeded(self, status: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        일일 한도 초과 여부 체크.
        Returns: (exceeded: bool, reason: str)
        """
        status = status or self.get_system_status()
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
    
    # =============================================
    # 월 사용량 / 급증 감지 (재발 방지)
    # =============================================

    def _get_month_key(self) -> str:
        """이번 달 키 (KST 기준, YYYY-MM)"""
        return self._get_today_key()[:7]

    def get_monthly_usage(self) -> Dict[str, Any]:
        """이번 달 누적 사용량 조회."""
        if not self.db:
            return {"month": self._get_month_key(), "calls": 0, "cost_usd": 0.0}
        try:
            month = self._get_month_key()
            doc = self.db.collection(MONTHLY_USAGE_COLLECTION).document(month).get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    "month": month,
                    "calls": data.get("calls", 0),
                    "cost_usd": data.get("cost_usd", 0.0),
                }
            return {"month": month, "calls": 0, "cost_usd": 0.0}
        except Exception as e:
            logger.error(f"Error getting monthly usage: {e}")
            return {"month": self._get_month_key(), "calls": 0, "cost_usd": 0.0}

    def check_monthly_limit_exceeded(self, status: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """월 비용 한도 초과 여부."""
        status = status or self.get_system_status()
        limit = status.get("monthly_limit_cost_usd", Config.MONTHLY_LIMIT_COST_USD)
        if not limit or limit <= 0:
            return False, ""
        current = self.get_monthly_usage().get("cost_usd", 0.0)
        if current >= limit:
            return True, f"월 비용 한도 초과 (${current:.2f}/${limit:.2f})"
        return False, ""

    def get_recent_daily_usages(self, days: int = 7) -> list:
        """오늘 제외, 최근 N일의 일일 사용량 목록 (존재하는 날짜만).

        지난 날짜 사용량은 하루가 지나면 불변이므로, 같은 날 동안 메모리에 캐시하여
        매 배치(5분)마다 동일 문서를 반복 조회하는 낭비를 막는다(자정 KST에 자동 무효화).
        """
        if not self.db:
            return []
        today = self._get_today_key()
        cache_key = (today, days)
        cached = getattr(self, "_recent_usage_cache", None)
        if cached and cached[0] == cache_key:
            return cached[1]
        from datetime import timedelta
        kst = timezone(timedelta(hours=9))
        base = datetime.now(kst)
        out = []
        for i in range(1, days + 1):
            d = (base - timedelta(days=i)).strftime("%Y-%m-%d")
            try:
                doc = self.db.collection(DAILY_USAGE_COLLECTION).document(d).get()
                if doc.exists:
                    data = doc.to_dict()
                    out.append({
                        "date": d,
                        "calls": data.get("calls", 0),
                        "cost_usd": data.get("cost_usd", 0.0),
                    })
            except Exception as e:
                logger.error(f"Error reading daily usage {d}: {e}")
        self._recent_usage_cache = (cache_key, out)
        return out

    def check_usage_spike(self, today_usage: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        """오늘 사용량이 최근 평균 대비 급증했는지 판정.

        고정 한도와 무관하게, 최근 며칠 평균 대비 오늘이 배수 이상 뛰면 급증으로 본다.
        특히 '통당 비용(cost/calls)' 급증은 코드/설정 변경으로 메일 1건당 비용이
        오른 상황(이번 7배 사례)을 잡아내는 핵심 지표다.

        Returns: (is_spike, detail)
        """
        if not self.db:
            return False, {}
        usage = today_usage or self.get_daily_usage()
        today_calls = usage.get("calls", 0) or 0
        today_cost = usage.get("cost_usd", 0.0) or 0.0

        min_calls = int(self.get_setting("usage_spike_min_calls", Config.USAGE_SPIKE_MIN_CALLS))
        if today_calls < min_calls:
            return False, {}

        recent = [r for r in self.get_recent_daily_usages(days=7) if (r.get("calls", 0) or 0) > 0]
        if len(recent) < 3:  # 표본 부족 시 판정 보류 (오탐 방지)
            return False, {}

        mult = float(self.get_setting("usage_spike_multiplier", Config.USAGE_SPIKE_MULTIPLIER))
        avg_cost = sum(r["cost_usd"] for r in recent) / len(recent)
        recent_cpc = sum(r["cost_usd"] / r["calls"] for r in recent) / len(recent)
        today_cpc = (today_cost / today_calls) if today_calls else 0.0

        spike_total = avg_cost > 0 and today_cost >= avg_cost * mult
        spike_cpc = recent_cpc > 0 and today_cpc >= recent_cpc * mult

        if spike_total or spike_cpc:
            return True, {
                "date": usage.get("date", self._get_today_key()),
                "today_cost": today_cost,
                "avg_cost": avg_cost,
                "today_cost_per_call": today_cpc,
                "recent_cost_per_call": recent_cpc,
                "multiplier": mult,
                "sample_days": len(recent),
                "kind": "통당 비용 급증" if spike_cpc else "총비용 급증",
            }
        return False, {}

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

        # 2. 일일 한도 체크 (status 재사용 — 중복 read 방지)
        exceeded, reason = self.check_daily_limit_exceeded(status)
        if exceeded:
            return False, reason

        # 3. 월 한도 체크 (status 재사용)
        m_exceeded, m_reason = self.check_monthly_limit_exceeded(status)
        if m_exceeded:
            return False, m_reason

        return True, "정상"

    # =============================================
    # 비용 알림 설정
    # =============================================

    def get_cost_alert_settings(self) -> Dict[str, Any]:
        """
        비용 알림 설정 조회 (system_settings/general TTL 캐시 경유).
        Returns: {
            "threshold_percent": float (0.0~1.0, 기본 0.8),
            "slack_channel": str (기본 변홍주 ID)
        }
        """
        # get_setting()은 5분 TTL 캐시를 경유하므로 Firestore 직접 읽기 불필요
        raw = self.get_setting("cost_alert_threshold_percent", 80)
        # UI에서 퍼센트(10-100) 또는 소수(0.1-1.0) 모두 허용
        threshold = float(raw) / 100.0 if float(raw) > 1.0 else float(raw)
        return {
            "threshold_percent": threshold,
            "slack_channel": self.get_setting("cost_alert_slack_channel") or DEFAULT_COST_ALERT_RECIPIENT,
        }

    def is_cost_alert_sent_today(self) -> bool:
        """오늘 이미 비용 알림을 보냈는지 확인"""
        if not self.db:
            return False
        try:
            today = self._get_today_key()
            doc = self.db.collection(DAILY_USAGE_COLLECTION).document(today).get()
            return bool((doc.to_dict() or {}).get("cost_alert_sent", False)) if doc.exists else False
        except Exception as e:
            logger.error(f"Error checking cost_alert_sent: {e}")
            return False

    def mark_cost_alert_sent_today(self) -> None:
        """오늘 비용 알림 전송 완료 표시 (중복 방지)"""
        if not self.db:
            return
        try:
            today = self._get_today_key()
            self.db.collection(DAILY_USAGE_COLLECTION).document(today).set(
                {"cost_alert_sent": True, "cost_alert_sent_at": datetime.now(timezone.utc).isoformat()},
                merge=True
            )
        except Exception as e:
            logger.error(f"Error marking cost_alert_sent: {e}")

    def is_spike_alert_sent_today(self) -> bool:
        """오늘 이미 급증 알림을 보냈는지 확인"""
        if not self.db:
            return False
        try:
            today = self._get_today_key()
            doc = self.db.collection(DAILY_USAGE_COLLECTION).document(today).get()
            return bool((doc.to_dict() or {}).get("spike_alert_sent", False)) if doc.exists else False
        except Exception as e:
            logger.error(f"Error checking spike_alert_sent: {e}")
            return False

    def mark_spike_alert_sent_today(self) -> None:
        """오늘 급증 알림 전송 완료 표시 (중복 방지)"""
        if not self.db:
            return
        try:
            today = self._get_today_key()
            self.db.collection(DAILY_USAGE_COLLECTION).document(today).set(
                {"spike_alert_sent": True, "spike_alert_sent_at": datetime.now(timezone.utc).isoformat()},
                merge=True
            )
        except Exception as e:
            logger.error(f"Error marking spike_alert_sent: {e}")

