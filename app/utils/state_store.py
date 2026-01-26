import json
import os
import threading
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from pathlib import Path
from app.utils.logger import get_logger

logger = get_logger("state_store")

# Firestore 관련 import (lazy loading으로 처리)
_firestore_client = None
_firestore_lock = threading.Lock()

class StateStore(ABC):
    @abstractmethod
    def get_last_fetched_time(self) -> datetime:
        """Get the timestamp of the last successfully processed batch."""
        pass

    @abstractmethod
    def set_last_fetched_time(self, timestamp: datetime):
        """Update the last fetched timestamp."""
        pass
        
    @abstractmethod
    def is_processed(self, message_id: str, target_id: str) -> bool:
        """Check if a specific notification for a message has already been sent."""
        pass
        
    @abstractmethod
    def is_duplicate_by_content(self, sender: str, subject: str, target_id: str, window_minutes: int = 10) -> bool:
        """Check if a notification with same sender/subject was recently sent to the target."""
        pass
        
    @abstractmethod
    def mark_processed(self, message_id: str, target_id: str, sender: str = None, subject: str = None):
        """Mark a notification as sent with optional content info for duplicate checking."""
        pass

class FileStateStore(StateStore):
    """
    Simple file-based state store for local dev / single instance Cloud Run (with volume).
    In production, this should be replaced by Firestore or Redis.
    """
    def __init__(self, file_path: str = "state.json"):
        self.file_path = Path(file_path)
        self.state = self._load()
        
    def _load(self) -> dict:
        if not self.file_path.exists():
            # Default to 10 minutes ago if no state exists
            return {
                "last_fetched_at": (datetime.utcnow() - timedelta(minutes=10)).isoformat(),
                "processed_ids": {},  # Key: message_id, Value: list of target_ids
            }
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load state file: {e}")
            return {
                "last_fetched_at": (datetime.utcnow() - timedelta(minutes=10)).isoformat(),
                "processed_ids": {},
            }

    def _save(self):
        try:
            with open(self.file_path, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state file: {e}")

    def get_last_fetched_time(self) -> datetime:
        ts_str = self.state.get("last_fetched_at")
        if ts_str:
            return datetime.fromisoformat(ts_str)
        return datetime.utcnow() - timedelta(minutes=10)

    def set_last_fetched_time(self, timestamp: datetime):
        self.state["last_fetched_at"] = timestamp.isoformat()
        self._save()

    def is_processed(self, message_id: str, target_id: str) -> bool:
        processed = self.state.get("processed_ids", {}).get(message_id, [])
        return target_id in processed

    def is_duplicate_by_content(self, sender: str, subject: str, target_id: str, window_minutes: int = 10) -> bool:
        # FileStateStore doesn't efficiently support time-windowed content checks
        # But for local dev, we can iterate through the last entries
        content_key = f"{sender}:{subject}"
        recent_cutoff = (datetime.utcnow() - timedelta(minutes=window_minutes)).isoformat()
        
        # Check against a (hypothetical) recent_content_notifications list
        # To keep it simple for FileStateStore, we'll just check everything
        recent_content = self.state.get("recent_content", {})
        if target_id in recent_content:
            for entry in recent_content[target_id]:
                if entry["content_key"] == content_key and entry["sent_at"] > recent_cutoff:
                    return True
        return False

    def mark_processed(self, message_id: str, target_id: str, sender: str = None, subject: str = None):
        if "processed_ids" not in self.state:
            self.state["processed_ids"] = {}
        
        if message_id not in self.state["processed_ids"]:
            self.state["processed_ids"][message_id] = []
            
        if target_id not in self.state["processed_ids"][message_id]:
            self.state["processed_ids"][message_id].append(target_id)
            
            # Also track recent content for throttling
            if sender and subject:
                if "recent_content" not in self.state:
                    self.state["recent_content"] = {}
                if target_id not in self.state["recent_content"]:
                    self.state["recent_content"][target_id] = []
                
                content_key = f"{sender}:{subject}"
                self.state["recent_content"][target_id].append({
                    "content_key": content_key,
                    "sent_at": datetime.utcnow().isoformat()
                })
                # Keep only last 100 entries per target
                self.state["recent_content"][target_id] = self.state["recent_content"][target_id][-100:]
                
            self._save()


def _get_firestore_client():
    """
    Get Firestore client with proper authentication for Cloud Run.
    Handles the case where GOOGLE_APPLICATION_CREDENTIALS is a JSON string.
    """
    global _firestore_client
    
    if _firestore_client is not None:
        return _firestore_client
    
    with _firestore_lock:
        if _firestore_client is not None:
            return _firestore_client
        
        try:
            from google.cloud import firestore
            from app.config import Config
            import google.auth
            from google.oauth2 import service_account
            
            if not Config.FIRESTORE_PROJECT_ID:
                logger.warning("FIRESTORE_PROJECT_ID not set. Firestore StateStore disabled.")
                return None
            
            logger.info(f"Initializing Firestore client for StateStore...")
            
            # GOOGLE_APPLICATION_CREDENTIALS가 JSON 문자열인 경우 처리
            creds_env = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            
            if creds_env and creds_env.startswith('{'):
                try:
                    import json
                    creds_info = json.loads(creds_env)
                    credentials = service_account.Credentials.from_service_account_info(creds_info)
                    logger.info("Initialized Firestore with JSON credentials from environment")
                except Exception as e:
                    logger.warning(f"Failed to parse GOOGLE_APPLICATION_CREDENTIALS as JSON: {e}")
                    credentials, project = google.auth.default()
            else:
                credentials, project = google.auth.default()
            
            _firestore_client = firestore.Client(
                project=Config.FIRESTORE_PROJECT_ID, 
                credentials=credentials
            )
            
            logger.info("Firestore client initialized successfully for StateStore")
            return _firestore_client
            
        except Exception as e:
            logger.error(f"Failed to initialize Firestore client for StateStore: {e}")
            return None


class FirestoreStateStore(StateStore):
    """
    Firestore-based state store for production Cloud Run deployment.
    Provides persistent storage across multiple instances.
    
    Collections:
    - processed_notifications: Stores message_id + target_id combinations
    - state_metadata: Stores last_fetched_time and other metadata
    """
    
    PROCESSED_COLLECTION = "processed_notifications"
    THROTTLING_COLLECTION = "notification_throttling" # New collection for content-based check
    METADATA_COLLECTION = "state_metadata"
    METADATA_DOC_ID = "global"
    
    # 7일 후 자동 삭제 (TTL)
    PROCESSED_TTL_DAYS = 7
    # 콘텐츠 기반 중복 방지 시간 (기본 10분)
    THROTTLING_TTL_MINUTES = 10
    
    def __init__(self):
        self.db = _get_firestore_client()
        if not self.db:
            logger.warning("Firestore not available. Falling back to in-memory state (중복 알림 발생 가능)")
            # 메모리 기반 fallback
            self._memory_state = {
                "last_fetched_at": (datetime.utcnow() - timedelta(minutes=10)).isoformat(),
                "processed_ids": {},
                "recent_content": {}
            }
    
    def get_last_fetched_time(self) -> datetime:
        if not self.db:
            ts_str = self._memory_state.get("last_fetched_at")
            return datetime.fromisoformat(ts_str) if ts_str else datetime.utcnow() - timedelta(minutes=10)
        
        try:
            doc = self.db.collection(self.METADATA_COLLECTION).document(self.METADATA_DOC_ID).get()
            if doc.exists:
                ts_str = doc.to_dict().get("last_fetched_at")
                if ts_str:
                    return datetime.fromisoformat(ts_str)
            return datetime.utcnow() - timedelta(minutes=10)
        except Exception as e:
            logger.error(f"Error getting last_fetched_time: {e}")
            return datetime.utcnow() - timedelta(minutes=10)

    def set_last_fetched_time(self, timestamp: datetime):
        if not self.db:
            self._memory_state["last_fetched_at"] = timestamp.isoformat()
            return
        
        try:
            self.db.collection(self.METADATA_COLLECTION).document(self.METADATA_DOC_ID).set({
                "last_fetched_at": timestamp.isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }, merge=True)
        except Exception as e:
            logger.error(f"Error setting last_fetched_time: {e}")

    def _make_doc_id(self, message_id: str, target_id: str) -> str:
        """Create a unique document ID from message_id and target_id."""
        # message_id에는 특수문자가 있을 수 있으므로 안전한 ID 생성
        import hashlib
        combined = f"{message_id}:{target_id}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def _make_throttling_id(self, sender: str, subject: str, target_id: str) -> str:
        """Create a unique document ID for content-based throttling."""
        import hashlib
        # normalize subject: remove whitespace
        normalized_subject = "".join(subject.split()) if subject else ""
        combined = f"{sender}:{normalized_subject}:{target_id}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def is_processed(self, message_id: str, target_id: str) -> bool:
        if not self.db:
            processed = self._memory_state.get("processed_ids", {}).get(message_id, [])
            return target_id in processed
        
        try:
            doc_id = self._make_doc_id(message_id, target_id)
            doc = self.db.collection(self.PROCESSED_COLLECTION).document(doc_id).get()
            return doc.exists
        except Exception as e:
            logger.error(f"Error checking is_processed: {e}")
            return False

    def is_duplicate_by_content(self, sender: str, subject: str, target_id: str, window_minutes: int = 10) -> bool:
        if not self.db:
            recent_content = self._memory_state.get("recent_content", {}).get(target_id, [])
            content_key = f"{sender}:{subject}"
            cutoff = (datetime.utcnow() - timedelta(minutes=window_minutes)).isoformat()
            for entry in recent_content:
                if entry["key"] == content_key and entry["sent_at"] > cutoff:
                    return True
            return False
            
        try:
            throttling_id = self._make_throttling_id(sender, subject, target_id)
            doc = self.db.collection(self.THROTTLING_COLLECTION).document(throttling_id).get()
            if doc.exists:
                data = doc.to_dict()
                sent_at = datetime.fromisoformat(data.get("sent_at"))
                if datetime.utcnow() - sent_at < timedelta(minutes=window_minutes):
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking is_duplicate_by_content: {e}")
            return False

    def mark_processed(self, message_id: str, target_id: str, sender: str = None, subject: str = None):
        if not self.db:
            if "processed_ids" not in self._memory_state:
                self._memory_state["processed_ids"] = {}
            if message_id not in self._memory_state["processed_ids"]:
                self._memory_state["processed_ids"][message_id] = []
            if target_id not in self._memory_state["processed_ids"][message_id]:
                self._memory_state["processed_ids"][message_id].append(target_id)
                
            if sender and subject:
                if "recent_content" not in self._memory_state:
                    self._memory_state["recent_content"] = {}
                if target_id not in self._memory_state["recent_content"]:
                    self._memory_state["recent_content"][target_id] = []
                self._memory_state["recent_content"][target_id].append({
                    "key": f"{sender}:{subject}",
                    "sent_at": datetime.utcnow().isoformat()
                })
            return
        
        try:
            doc_id = self._make_doc_id(message_id, target_id)
            expire_at = datetime.utcnow() + timedelta(days=self.PROCESSED_TTL_DAYS)
            
            # 1. RFC822 Message-ID 기반 중복 방지 기록
            self.db.collection(self.PROCESSED_COLLECTION).document(doc_id).set({
                "message_id": message_id,
                "target_id": target_id,
                "processed_at": datetime.utcnow().isoformat(),
                "expire_at": expire_at.isoformat()
            })
            
            # 2. 콘텐츠 기반 중복 방지(Throttling) 기록
            if sender and subject:
                throttling_id = self._make_throttling_id(sender, subject, target_id)
                self.db.collection(self.THROTTLING_COLLECTION).document(throttling_id).set({
                    "sender": sender,
                    "subject": subject,
                    "target_id": target_id,
                    "sent_at": datetime.utcnow().isoformat(),
                    # 1시간 정도만 유지하면 충분
                    "expire_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
                })
                
            logger.info(f"Marked as processed: {message_id} -> {target_id} (Content tracking: {bool(sender)})")
        except Exception as e:
            logger.error(f"Error marking as processed: {e}")


def create_state_store() -> StateStore:
    """
    Factory function to create the appropriate state store.
    Uses Firestore in production (Cloud Run), File-based for local development.
    """
    from app.config import Config
    
    # Firestore 프로젝트 ID가 설정되어 있으면 Firestore 사용 시도
    if Config.FIRESTORE_PROJECT_ID:
        logger.info("Attempting to use FirestoreStateStore...")
        store = FirestoreStateStore()
        if store.db:
            logger.info("FirestoreStateStore initialized successfully")
            return store
        else:
            logger.warning("Firestore not available, falling back to FileStateStore")
    
    # Fallback to FileStateStore
    logger.info("Using FileStateStore (local/development mode)")
    return FileStateStore()

