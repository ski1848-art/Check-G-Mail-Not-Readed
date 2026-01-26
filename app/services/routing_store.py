import time
import threading
from typing import Dict, List, Optional
from google.cloud import firestore
from app.config import Config
from app.utils.logger import get_logger
from app.models import NotificationTarget

logger = get_logger("routing_store")

class RoutingStore:
    """
    Manages routing rules from Firestore with TTL caching.
    Maps Gmail accounts to Slack notification targets.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(RoutingStore, cls).__new__(cls)
                    cls._instance._init_store()
        return cls._instance

    def _init_store(self):
        self.db = None
        if Config.FIRESTORE_PROJECT_ID:
            try:
                logger.info(f"Initializing Firestore client for project: {Config.FIRESTORE_PROJECT_ID}")
                # Cloud Run에서 GOOGLE_APPLICATION_CREDENTIALS가 Secret으로 주입되면
                # google.auth.default()가 이를 파일로 읽으려고 시도하여 에러 발생
                # 해결: 임시로 환경변수를 제거하고 메타데이터 서버 기반 인증 사용
                import google.auth
                import os
                
                # GOOGLE_APPLICATION_CREDENTIALS를 백업 후 제거
                creds_backup = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
                if creds_backup and creds_backup.startswith('{'):
                    # JSON 문자열인 경우 (Secret Manager에서 주입)
                    del os.environ['GOOGLE_APPLICATION_CREDENTIALS']
                    logger.info("Temporarily removed GOOGLE_APPLICATION_CREDENTIALS (JSON string) for Firestore initialization")
                
                # 메타데이터 서버 기반 인증 사용
                credentials, project = google.auth.default()
                self.db = firestore.Client(project=Config.FIRESTORE_PROJECT_ID, credentials=credentials)
                
                # 환경변수 복원 (Gmail Service에서 사용)
                if creds_backup:
                    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_backup
                
                logger.info(f"Firestore client initialized successfully for project: {Config.FIRESTORE_PROJECT_ID}")
            except Exception as e:
                logger.error(f"Failed to initialize Firestore client: {e}", exc_info=True)
        else:
            logger.warning("FIRESTORE_PROJECT_ID not set. Firestore routing disabled.")
        
        self.cache: Dict[str, List[str]] = {}  # gmail_email -> List[slack_user_id]
        self.last_updated = 0
        self.cache_ttl = Config.ROUTING_CACHE_TTL_SEC

    def get_targets_for_gmail(self, gmail_email: str) -> List[NotificationTarget]:
        """
        Get Slack targets for a given Gmail account.
        Uses cached data if available and not expired.
        """
        self._refresh_cache_if_needed()
        
        slack_user_ids = self.cache.get(gmail_email.lower().strip(), [])
        targets = []
        for user_id in slack_user_ids:
            targets.append(NotificationTarget(target_id=user_id, target_type="user"))
            
        return targets

    def _refresh_cache_if_needed(self):
        now = time.time()
        if now - self.last_updated > self.cache_ttl:
            with self._lock:
                # Double-check inside lock
                if now - self.last_updated > self.cache_ttl:
                    self._load_from_firestore()
                    self.last_updated = time.time()

    def _load_from_firestore(self):
        if not self.db:
            logger.warning("Firestore client not initialized. Cannot load routing rules.")
            return

        try:
            logger.info("Refreshing routing rules from Firestore...")
            new_cache: Dict[str, List[str]] = {}
            
            # Collection: routing_rules
            # Document ID: slack_user_id
            rules_ref = self.db.collection("routing_rules")
            docs = rules_ref.where("enabled", "==", True).stream()
            
            count = 0
            for doc in docs:
                data = doc.to_dict()
                slack_user_id = data.get("slack_user_id")
                gmail_accounts = data.get("gmail_accounts", [])
                
                if not slack_user_id:
                    continue
                
                for gmail in gmail_accounts:
                    normalized_gmail = gmail.lower().strip()
                    if normalized_gmail not in new_cache:
                        new_cache[normalized_gmail] = []
                    if slack_user_id not in new_cache[normalized_gmail]:
                        new_cache[normalized_gmail].append(slack_user_id)
                count += 1
            
            self.cache = new_cache
            logger.info(f"Loaded {count} enabled routing rules from Firestore. Total unique Gmails: {len(self.cache)}")
            
        except Exception as e:
            logger.error(f"Error loading routing rules from Firestore: {e}")
            # Keep old cache on error

    def get_all_monitored_emails(self) -> List[str]:
        """
        Get all Gmail accounts that should be monitored.
        Returns a deduplicated list of all Gmail addresses from enabled users.
        """
        self._refresh_cache_if_needed()
        return list(self.cache.keys())
