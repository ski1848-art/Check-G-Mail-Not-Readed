"""
Learning Store Service - Firestore 기반 학습 데이터 저장소

이 모듈은 Implicit Feedback 기반 자동학습을 위해:
1. 메일 이벤트 스냅샷 저장 (email_events)
2. 사용자 행동 로그 저장 (engagement_events)
3. 조직/개인 Prior 계산 및 저장 (priors_org, priors_user)

Firestore 장애 시에도 메인 알림 파이프라인은 계속 동작해야 함.
모든 Firestore 작업은 try/except로 감싸고 warning 로그만 남김.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from app.config import Config
from app.utils.logger import get_logger

logger = get_logger("learning_store")

# Firestore 클라이언트 (lazy initialization)
_firestore_client = None


def _get_firestore_client():
    """
    Firestore 클라이언트를 lazy하게 초기화.
    LEARNING_ENABLED=false이거나 Firestore 사용 불가 시 None 반환.
    """
    global _firestore_client
    
    if not Config.LEARNING_ENABLED:
        return None
    
    if _firestore_client is not None:
        return _firestore_client
    
    try:
        from google.cloud import firestore
        import google.auth
        from google.oauth2 import service_account
        import os
        import json
        
        project_id = Config.FIRESTORE_PROJECT_ID or None
        
        # GOOGLE_APPLICATION_CREDENTIALS가 JSON 문자열인 경우 직접 파싱
        creds_env = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        
        if creds_env and creds_env.startswith('{'):
            try:
                creds_info = json.loads(creds_env)
                credentials = service_account.Credentials.from_service_account_info(creds_info)
                logger.info("Initialized Firestore with JSON credentials from environment")
            except Exception as e:
                logger.warning(f"Failed to parse GOOGLE_APPLICATION_CREDENTIALS as JSON: {e}")
                credentials, project = google.auth.default()
        else:
            credentials, project = google.auth.default()
        
        _firestore_client = firestore.Client(project=project_id, credentials=credentials)
        logger.info(f"Firestore client initialized for learning_store (project: {project_id or 'default'})")
        return _firestore_client
    except Exception as e:
        logger.warning(f"Failed to initialize Firestore client for learning_store: {e}")
        return None


# =============================================
# Collection Names
# =============================================
COLLECTION_EMAIL_EVENTS = "email_events"
COLLECTION_ENGAGEMENT_EVENTS = "engagement_events"
COLLECTION_PRIORS_ORG = "priors_org"
COLLECTION_PRIORS_USER = "priors_user"
COLLECTION_USER_FEEDBACK = "user_feedback"


# =============================================
# User Explicit Feedback (사용자 명시적 피드백)
# =============================================

def extract_email_type_pattern(subject: Optional[str]) -> str:
    """
    메일 제목에서 "유형 패턴"을 추출.
    변동되는 부분(이름, 도메인명 등)을 제거하고 핵심 유형만 남김.
    
    예시:
    - "[그리팅] 김한지 님이 ... 지원했습니다" → "[그리팅] 채용 지원 알림"
    - "[NHN Domain] whatsell.co.kr 도메인명 기간연장 안내" → "[NHN Domain] 도메인 기간연장 안내"
    - "Re: 회의 일정 조율" → "Re: 회의 관련"
    """
    import re
    
    if not subject:
        return "일반 메일"
    
    original = subject.strip()
    
    # 1. 접두사 추출 (예: [그리팅], [NHN Domain], Re:, Fwd:)
    prefix_match = re.match(r'^(\[.+?\]|Re:|RE:|Fwd:|FW:)\s*', original)
    prefix = prefix_match.group(1) if prefix_match else ""
    rest = original[len(prefix_match.group(0)):] if prefix_match else original
    
    # 2. 알려진 패턴 매칭 (우선순위 높음)
    patterns = [
        # 그리팅 채용 관련
        (r'.*님이.*지원.*', '채용 지원 알림'),
        (r'.*지원.*공고.*', '채용 지원 알림'),
        (r'.*면접.*일정.*', '면접 일정 안내'),
        (r'.*채용.*마감.*', '채용 마감 안내'),
        
        # 도메인/호스팅 관련
        (r'.*도메인.*기간.*연장.*', '도메인 기간연장 안내'),
        (r'.*도메인.*만료.*', '도메인 만료 안내'),
        (r'.*호스팅.*연장.*', '호스팅 연장 안내'),
        
        # 결제/정산 관련
        (r'.*결제.*실패.*', '결제 실패 안내'),
        (r'.*결제.*완료.*', '결제 완료 안내'),
        (r'.*정산.*신청.*', '정산 신청'),
        (r'.*청구서.*', '청구서'),
        (r'.*인보이스.*', '인보이스'),
        
        # 알림/리포트
        (r'.*일일.*리포트.*', '일일 리포트'),
        (r'.*주간.*리포트.*', '주간 리포트'),
        (r'.*월간.*리포트.*', '월간 리포트'),
        (r'.*알림.*설정.*', '알림 설정'),
        
        # 뉴스레터/마케팅
        (r'.*뉴스레터.*', '뉴스레터'),
        (r'.*newsletter.*', '뉴스레터'),
        (r'.*프로모션.*', '프로모션'),
        (r'.*할인.*', '프로모션'),
    ]
    
    rest_lower = rest.lower()
    for pattern, label in patterns:
        if re.match(pattern, rest_lower, re.IGNORECASE):
            return f"{prefix} {label}".strip() if prefix else label
    
    # 3. 동적 부분 제거 (이름, 도메인, 숫자 등)
    # 한글 이름 패턴 (2-4글자)
    cleaned = re.sub(r'[가-힣]{2,4}\s*님', '*님', rest)
    # 도메인 패턴
    cleaned = re.sub(r'[a-zA-Z0-9-]+\.(co\.kr|com|net|org|kr|biz)', '*', cleaned)
    # 날짜 패턴
    cleaned = re.sub(r'\d{4}[-/]\d{2}[-/]\d{2}', '*', cleaned)
    cleaned = re.sub(r'\d{1,2}월\s*\d{1,2}일', '*', cleaned)
    # 숫자 (금액, ID 등)
    cleaned = re.sub(r'\d{3,}', '*', cleaned)
    # 연속 공백 정리
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # 4. 너무 길면 앞부분만
    if len(cleaned) > 30:
        cleaned = cleaned[:30] + "..."
    
    result = f"{prefix} {cleaned}".strip() if prefix else cleaned
    return result if result else "일반 메일"


def save_user_silent_preference(user_id: str, sender: str, subject: Optional[str] = None) -> bool:
    """
    사용자가 특정 발신자의 특정 유형 메일을 '알림 불필요'로 지정했음을 저장.
    subject에서 유형 패턴을 추출하여 저장.
    """
    db = _get_firestore_client()
    if db is None:
        return False
    
    try:
        # 제목에서 유형 패턴 추출
        type_pattern = extract_email_type_pattern(subject)
        
        # User ID와 Sender, 유형 패턴을 조합하여 고유한 문서 ID 생성
        import hashlib
        combined = f"{user_id}_{sender}_{type_pattern}"
        doc_id = hashlib.sha256(combined.encode()).hexdigest()[:32]
        
        doc_ref = db.collection(COLLECTION_USER_FEEDBACK).document(doc_id)
        
        doc_data = {
            "user_id": user_id,
            "sender": sender,
            "subject_pattern": type_pattern,  # 추출된 유형 패턴
            "original_subject": subject[:200] if subject else None,  # 원본 제목 (디버깅용)
            "preference": "silent",
            "created_at": datetime.utcnow().isoformat()
        }
        doc_ref.set(doc_data)
        logger.info(f"Saved user preference: {user_id} wants silent for {sender} (type: {type_pattern})")
        return True
    except Exception as e:
        logger.warning(f"Failed to save user preference: {e}")
        return False


def delete_user_silent_preference(user_id: str, sender: str, subject: Optional[str] = None) -> bool:
    """
    사용자가 이전에 차단했던 선호도를 삭제 (알림 다시 받기).
    subject에서 유형 패턴을 추출하여 매칭.
    """
    db = _get_firestore_client()
    if db is None:
        return False
    
    try:
        import hashlib
        # 제목에서 유형 패턴 추출 (저장할 때와 동일한 방식)
        type_pattern = extract_email_type_pattern(subject)
        combined = f"{user_id}_{sender}_{type_pattern}"
        doc_id = hashlib.sha256(combined.encode()).hexdigest()[:32]
        
        db.collection(COLLECTION_USER_FEEDBACK).document(doc_id).delete()
        logger.info(f"Deleted user preference (Undo Silent): {user_id} now accepts {sender} (type: {type_pattern})")
        return True
    except Exception as e:
        logger.warning(f"Failed to delete user preference: {e}")
        return False


def get_user_silent_preferences(user_id: str) -> List[Dict[str, Any]]:
    """
    특정 사용자의 모든 '알림 불필요' 선호도 조회.
    """
    db = _get_firestore_client()
    if db is None:
        return []
    
    try:
        query = db.collection(COLLECTION_USER_FEEDBACK).where("user_id", "==", user_id)
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.warning(f"Failed to get user preferences: {e}")
        return []


def should_silence_for_user(user_id: str, sender: str, subject: str) -> bool:
    """
    사용자의 차단 목록과 현재 메일을 비교하여 차단 여부를 규칙 기반으로 판단.
    LLM에 의존하지 않고 직접 매칭.
    
    Returns:
        True: 이 사용자에게 알림 보내지 않아야 함
        False: 정상적으로 알림 보내도 됨
    """
    prefs = get_user_silent_preferences(user_id)
    if not prefs:
        return False
    
    current_pattern = extract_email_type_pattern(subject)
    current_sender = (sender or "").lower().strip()
    
    for pref in prefs:
        pref_sender = (pref.get("sender") or "").lower().strip()
        pref_pattern = pref.get("subject_pattern")
        
        # 발신자가 다르면 스킵
        if pref_sender != current_sender:
            continue
        
        # subject_pattern이 null인 경우 (이전 코드로 저장된 데이터)
        # → 발신자만 일치하면 차단 (하위 호환)
        if not pref_pattern:
            logger.info(f"[SILENCE] User {user_id}: sender match (legacy null pattern) for {sender}")
            return True
        
        # 유형 패턴 매칭
        if pref_pattern == current_pattern:
            logger.info(f"[SILENCE] User {user_id}: exact pattern match '{current_pattern}' for {sender}")
            return True
        
        # 부분 매칭 (패턴의 핵심 키워드가 현재 패턴에 포함되는지)
        # 예: "도메인 기간연장 안내" vs "[NHN Domain] 도메인 기간연장 안내"
        pref_keywords = set(pref_pattern.replace("[", "").replace("]", "").split())
        current_keywords = set(current_pattern.replace("[", "").replace("]", "").split())
        
        # 핵심 키워드 3개 이상 겹치면 같은 유형으로 판단
        overlap = pref_keywords & current_keywords
        if len(overlap) >= 3:
            logger.info(f"[SILENCE] User {user_id}: keyword overlap match ({overlap}) for {sender}")
            return True
    
    return False
def save_email_event_snapshot(
    email_id: str,
    subject: str,
    from_email: str,
    from_domain: str,
    to_email: str,
    timestamp: datetime,
    rule_decision: Optional[str],  # RULE_CRITICAL, RULE_IGNORE, UNDECIDED
    llm_score_raw: Optional[float],
    llm_category_raw: Optional[str],
    llm_score_adjusted: Optional[float],
    prior_used: Optional[str],  # org, user, none
    prior_value: Optional[float],
    alpha_used: Optional[float],
    final_category: str,
    slack_targets: List[str],
    reason: Optional[str] = None,  # AI 판별 사유
    summary: Optional[str] = None,  # AI 핵심 요약
    thread_id: Optional[str] = None,
    canonical_message_id: Optional[str] = None,
    # 토큰 사용량 (비용 추적용)
    llm_input_tokens: Optional[int] = None,
    llm_output_tokens: Optional[int] = None,
    llm_cache_read_tokens: Optional[int] = None,
    llm_cache_write_tokens: Optional[int] = None,
) -> bool:
    """
    메일 처리 결과를 Firestore에 스냅샷으로 저장.
    
    Returns:
        bool: 저장 성공 여부
    """
    db = _get_firestore_client()
    if db is None:
        return False
    
    try:
        doc_ref = db.collection(COLLECTION_EMAIL_EVENTS).document(email_id)
        doc_data = {
            "email_id": email_id,
            "thread_id": thread_id,
            "canonical_message_id": canonical_message_id,
            "subject": subject[:200] if subject else None,  # 제목만 저장 (본문 X)
            "from_email": from_email,
            "from_domain": from_domain,
            "to_email": to_email,
            "timestamp": timestamp,
            "rule_decision": rule_decision,
            "llm_score_raw": llm_score_raw,
            "llm_category_raw": llm_category_raw,
            "llm_score_adjusted": llm_score_adjusted,
            "prior_used": prior_used,
            "prior_value": prior_value,
            "alpha_used": alpha_used,
            "final_category": final_category,
            "slack_targets": slack_targets,
            "reason": reason,  # AI 판별 사유
            "summary": summary,  # AI 핵심 요약
            "created_at": datetime.utcnow(),
            # 토큰 사용량 (비용 추적용)
            "llm_input_tokens": llm_input_tokens,
            "llm_output_tokens": llm_output_tokens,
            "llm_cache_read_tokens": llm_cache_read_tokens,
            "llm_cache_write_tokens": llm_cache_write_tokens,
        }
        doc_ref.set(doc_data)
        logger.debug(f"Saved email event snapshot: {email_id}")
        return True
    except Exception as e:
        logger.warning(f"Failed to save email event snapshot {email_id}: {e}")
        return False


def get_email_event(email_id: str) -> Optional[Dict[str, Any]]:
    """
    저장된 메일 이벤트 스냅샷 조회.
    """
    db = _get_firestore_client()
    if db is None:
        return None
    
    try:
        doc_ref = db.collection(COLLECTION_EMAIL_EVENTS).document(email_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.warning(f"Failed to get email event {email_id}: {e}")
        return None


# =============================================
# Engagement Events (사용자 행동 로그)
# =============================================
def log_engagement_event(
    user_email: str,
    email_id: str,
    event_type: str,  # slack_click_open, gmail_read
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    사용자 행동 이벤트를 Firestore에 기록.
    
    event_type:
        - slack_click_open: Slack에서 Gmail 열기 클릭
        - gmail_read: Gmail에서 메일 읽음
    
    Returns:
        bool: 저장 성공 여부
    """
    db = _get_firestore_client()
    if db is None:
        return False
    
    try:
        doc_ref = db.collection(COLLECTION_ENGAGEMENT_EVENTS).document()
        doc_data = {
            "email_id": email_id,
            "user_email": user_email,
            "event_type": event_type,
            "event_ts": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        doc_ref.set(doc_data)
        logger.debug(f"Logged engagement event: {event_type} for {email_id} by {user_email}")
        return True
    except Exception as e:
        logger.warning(f"Failed to log engagement event: {e}")
        return False


def get_engagement_events(
    email_id: Optional[str] = None,
    user_email: Optional[str] = None,
    from_email: Optional[str] = None,
    from_domain: Optional[str] = None,
    since_days: int = 7,
) -> List[Dict[str, Any]]:
    """
    engagement_events 조회 (Prior 계산용).
    
    Args:
        email_id: 특정 메일 ID로 필터
        user_email: 특정 사용자로 필터
        from_email: 특정 발신자로 필터 (email_events JOIN 필요)
        from_domain: 특정 도메인으로 필터 (email_events JOIN 필요)
        since_days: 최근 N일 데이터만
    
    Returns:
        List of engagement event dicts
    """
    db = _get_firestore_client()
    if db is None:
        return []
    
    try:
        # 기본 쿼리 (최근 N일)
        cutoff = datetime.utcnow() - timedelta(days=since_days)
        cutoff_str = cutoff.isoformat()
        
        query = db.collection(COLLECTION_ENGAGEMENT_EVENTS)
        query = query.where("event_ts", ">=", cutoff_str)
        
        if email_id:
            query = query.where("email_id", "==", email_id)
        if user_email:
            query = query.where("user_email", "==", user_email)
        
        docs = query.stream()
        results = [doc.to_dict() for doc in docs]
        
        # from_email/from_domain 필터는 email_events와 JOIN 필요
        # (Firestore는 JOIN 지원 안 함, 클라이언트에서 처리)
        if from_email or from_domain:
            filtered = []
            for event in results:
                email_event = get_email_event(event.get("email_id", ""))
                if email_event:
                    if from_email and email_event.get("from_email") == from_email:
                        filtered.append(event)
                    elif from_domain and email_event.get("from_domain") == from_domain:
                        filtered.append(event)
            results = filtered
        
        return results
    except Exception as e:
        logger.warning(f"Failed to get engagement events: {e}")
        return []


# =============================================
# Organization Prior (조직 단위 신뢰도)
# =============================================
def get_org_prior(from_email: str, from_domain: str) -> Tuple[Optional[float], int, str]:
    """
    조직 단위 Prior 조회.
    
    우선순위: from_email(sender) > from_domain(domain)
    
    Args:
        from_email: 발신자 이메일
        from_domain: 발신자 도메인
    
    Returns:
        Tuple of (prior, samples, source)
        - prior: 0~1 float (None if not found or insufficient samples)
        - samples: 표본수
        - source: "sender", "domain", or "none"
    """
    db = _get_firestore_client()
    if db is None:
        return None, 0, "none"
    
    try:
        # 1. from_email로 먼저 조회
        sender_doc = db.collection(COLLECTION_PRIORS_ORG).document(from_email).get()
        if sender_doc.exists:
            data = sender_doc.to_dict()
            samples = data.get("samples", 0)
            if samples >= Config.PRIOR_MIN_SAMPLES:
                return data.get("prior"), samples, "sender"
        
        # 2. from_domain으로 조회
        domain_doc = db.collection(COLLECTION_PRIORS_ORG).document(from_domain).get()
        if domain_doc.exists:
            data = domain_doc.to_dict()
            samples = data.get("samples", 0)
            if samples >= Config.PRIOR_MIN_SAMPLES:
                return data.get("prior"), samples, "domain"
        
        return None, 0, "none"
    except Exception as e:
        logger.warning(f"Failed to get org prior: {e}")
        return None, 0, "none"


def upsert_prior_org(key_type: str, key_value: str, prior: float, samples: int) -> bool:
    """
    조직 단위 Prior 저장/업데이트.
    
    Args:
        key_type: "sender" or "domain"
        key_value: 이메일 주소 또는 도메인
        prior: 0~1 float
        samples: 표본수
    
    Returns:
        bool: 저장 성공 여부
    """
    db = _get_firestore_client()
    if db is None:
        return False
    
    try:
        doc_ref = db.collection(COLLECTION_PRIORS_ORG).document(key_value)
        doc_data = {
            "key_type": key_type,
            "key_value": key_value,
            "prior": prior,
            "samples": samples,
            "updated_at": datetime.utcnow().isoformat(),
        }
        doc_ref.set(doc_data)
        logger.debug(f"Upserted org prior: {key_value} = {prior:.3f} (n={samples})")
        return True
    except Exception as e:
        logger.warning(f"Failed to upsert org prior: {e}")
        return False


# =============================================
# User Prior (개인 단위 신뢰도)
# =============================================
def _make_user_prior_key(user_email: str, key_value: str) -> str:
    """개인 prior의 문서 ID 생성: {user_email}__{key_value}"""
    return f"{user_email}__{key_value}"


def get_user_prior(user_email: str, from_email: str, from_domain: str) -> Tuple[Optional[float], int, str]:
    """
    개인 단위 Prior 조회.
    
    우선순위: from_email(sender) > from_domain(domain)
    
    Args:
        user_email: 알림 받는 사용자 이메일
        from_email: 발신자 이메일
        from_domain: 발신자 도메인
    
    Returns:
        Tuple of (prior, samples, source)
    """
    db = _get_firestore_client()
    if db is None:
        return None, 0, "none"
    
    try:
        # 1. user + from_email로 먼저 조회
        sender_key = _make_user_prior_key(user_email, from_email)
        sender_doc = db.collection(COLLECTION_PRIORS_USER).document(sender_key).get()
        if sender_doc.exists:
            data = sender_doc.to_dict()
            samples = data.get("samples", 0)
            if samples >= Config.PRIOR_MIN_SAMPLES:
                return data.get("prior"), samples, "sender"
        
        # 2. user + from_domain으로 조회
        domain_key = _make_user_prior_key(user_email, from_domain)
        domain_doc = db.collection(COLLECTION_PRIORS_USER).document(domain_key).get()
        if domain_doc.exists:
            data = domain_doc.to_dict()
            samples = data.get("samples", 0)
            if samples >= Config.PRIOR_MIN_SAMPLES:
                return data.get("prior"), samples, "domain"
        
        return None, 0, "none"
    except Exception as e:
        logger.warning(f"Failed to get user prior: {e}")
        return None, 0, "none"


def upsert_prior_user(user_email: str, key_type: str, key_value: str, prior: float, samples: int) -> bool:
    """
    개인 단위 Prior 저장/업데이트.
    
    Args:
        user_email: 사용자 이메일
        key_type: "sender" or "domain"
        key_value: 이메일 주소 또는 도메인
        prior: 0~1 float
        samples: 표본수
    
    Returns:
        bool: 저장 성공 여부
    """
    db = _get_firestore_client()
    if db is None:
        return False
    
    try:
        doc_key = _make_user_prior_key(user_email, key_value)
        doc_ref = db.collection(COLLECTION_PRIORS_USER).document(doc_key)
        doc_data = {
            "user_email": user_email,
            "key_type": key_type,
            "key_value": key_value,
            "prior": prior,
            "samples": samples,
            "updated_at": datetime.utcnow().isoformat(),
        }
        doc_ref.set(doc_data)
        logger.debug(f"Upserted user prior: {user_email}/{key_value} = {prior:.3f} (n={samples})")
        return True
    except Exception as e:
        logger.warning(f"Failed to upsert user prior: {e}")
        return False


# =============================================
# Prior Calculation Logic (Engagement 점수화)
# =============================================
def calculate_engagement_score(events: List[Dict[str, Any]]) -> float:
    """
    여러 engagement 이벤트들의 점수를 합산.
    
    점수 기준 (Config에서 튜닝 가능):
        - gmail_read (10분 내): +1.0
        - gmail_read (2시간 내): +0.5
        - slack_click_open: +0.2
    
    Args:
        events: engagement_events 리스트
    
    Returns:
        총 점수
    """
    total_score = 0.0
    
    for event in events:
        event_type = event.get("event_type", "")
        metadata = event.get("metadata", {})
        
        if event_type == "gmail_read":
            latency_sec = metadata.get("latency_sec", float("inf"))
            if latency_sec <= Config.IMPLICIT_POS_READ_MIN * 60:
                total_score += Config.IMPLICIT_SCORE_READ_STRONG
            elif latency_sec <= Config.IMPLICIT_POS_READ_2H * 60:
                total_score += Config.IMPLICIT_SCORE_READ_WEAK
            # else: neutral (0)
        elif event_type == "slack_click_open":
            total_score += Config.IMPLICIT_SCORE_CLICK
    
    return total_score


def calculate_prior_from_scores(scores: List[float], positive_threshold: float = 0.7) -> Tuple[float, int]:
    """
    개별 이메일 점수들로부터 prior를 계산.
    
    Args:
        scores: 각 이메일별 engagement score 리스트
        positive_threshold: 이 점수 이상이면 positive로 카운트
    
    Returns:
        Tuple of (prior, samples)
        prior = positive_count / (positive_count + negative_count)
    """
    positive_count = 0
    negative_count = 0
    
    for score in scores:
        if score >= positive_threshold:
            positive_count += 1
        elif score <= 0:
            negative_count += 1
        # 0 < score < threshold: neutral, ignore
    
    samples = positive_count + negative_count
    if samples == 0:
        return Config.BASELINE_PRIOR, 0
    
    prior = positive_count / samples
    return prior, samples


# =============================================
# Prior Update Job (배치에서 호출)
# =============================================
def update_priors_for_sender(from_email: str, from_domain: str, since_days: int = 7) -> bool:
    """
    특정 발신자에 대한 조직 Prior를 업데이트.
    
    Args:
        from_email: 발신자 이메일
        from_domain: 발신자 도메인
        since_days: 최근 N일 데이터 사용
    
    Returns:
        bool: 업데이트 성공 여부
    """
    db = _get_firestore_client()
    if db is None:
        return False
    
    try:
        # 1. 해당 발신자의 모든 email_events 조회
        cutoff = datetime.utcnow() - timedelta(days=since_days)
        cutoff_str = cutoff.isoformat()
        
        email_events = db.collection(COLLECTION_EMAIL_EVENTS) \
            .where("from_email", "==", from_email) \
            .where("created_at", ">=", cutoff_str) \
            .stream()
        
        email_ids = [doc.to_dict().get("email_id") for doc in email_events]
        
        if not email_ids:
            return True  # Nothing to update
        
        # 2. 각 이메일별 engagement score 계산
        scores = []
        for email_id in email_ids:
            events = get_engagement_events(email_id=email_id, since_days=since_days)
            score = calculate_engagement_score(events)
            scores.append(score)
        
        # 3. Prior 계산
        prior, samples = calculate_prior_from_scores(scores)
        
        # 4. 저장 (samples >= min_samples 조건은 조회 시 체크)
        if samples > 0:
            upsert_prior_org("sender", from_email, prior, samples)
        
        return True
    except Exception as e:
        logger.warning(f"Failed to update priors for sender {from_email}: {e}")
        return False


def update_all_priors(since_days: int = 7, limit: int = 1000) -> Dict[str, int]:
    """
    최근 활성 발신자들의 Prior를 일괄 업데이트.
    매 배치 마지막에 호출.
    
    Args:
        since_days: 최근 N일 데이터 사용
        limit: 최대 처리할 발신자 수 (성능 제한)
    
    Returns:
        Dict with counts: {"updated": N, "failed": M}
    """
    db = _get_firestore_client()
    if db is None:
        return {"updated": 0, "failed": 0}
    
    try:
        # 최근 engagement가 있는 email_id 수집
        cutoff = datetime.utcnow() - timedelta(days=since_days)
        cutoff_str = cutoff.isoformat()
        
        engagement_docs = db.collection(COLLECTION_ENGAGEMENT_EVENTS) \
            .where("event_ts", ">=", cutoff_str) \
            .limit(limit) \
            .stream()
        
        # email_id → from_email/domain 매핑
        senders = set()
        for doc in engagement_docs:
            email_id = doc.to_dict().get("email_id")
            if email_id:
                email_event = get_email_event(email_id)
                if email_event:
                    from_email = email_event.get("from_email")
                    from_domain = email_event.get("from_domain")
                    if from_email:
                        senders.add((from_email, from_domain or ""))
        
        # 각 발신자에 대해 prior 업데이트
        updated = 0
        failed = 0
        for from_email, from_domain in senders:
            success = update_priors_for_sender(from_email, from_domain, since_days)
            if success:
                updated += 1
            else:
                failed += 1
        
        logger.info(f"Prior update complete: {updated} updated, {failed} failed")
        return {"updated": updated, "failed": failed}
    except Exception as e:
        logger.warning(f"Failed to update all priors: {e}")
        return {"updated": 0, "failed": 0}


# =============================================
# Read Status Tracking (읽음 상태 추적)
# =============================================
def update_first_read_detected(email_id: str, user_email: str, notified_at: datetime) -> bool:
    """
    Gmail에서 메일이 처음 읽힌 것이 감지되었을 때 호출.
    latency를 계산하고 engagement 이벤트를 기록.
    
    Args:
        email_id: 메일 ID
        user_email: 알림 받은 사용자
        notified_at: 최초 알림 시각
    
    Returns:
        bool: 성공 여부
    """
    now = datetime.utcnow()
    latency_sec = (now - notified_at).total_seconds()
    
    return log_engagement_event(
        user_email=user_email,
        email_id=email_id,
        event_type="gmail_read",
        metadata={"latency_sec": latency_sec, "detected_at": now.isoformat()}
    )
