"""
models.py - Pydantic 데이터 모델 정의

이메일 처리 파이프라인에서 사용되는 핵심 데이터 구조.

[모델 관계]
  GmailEvent (입력) → Classifier → AnalysisResult (분석 결과)
  GmailEvent + AnalysisResult → Router → NotificationTarget (알림 대상)
  모든 것을 합쳐서 → ProcessedResult (최종 처리 결과, 로깅/디버깅용)
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

class ImportanceCategory(str, Enum):
    """이메일 중요도 분류 결과 (2단계)"""
    NOTIFY = "notify"   # 알림 전송 대상
    SILENT = "silent"   # 무시 (알림 안 보냄)

class AnalysisSource(str, Enum):
    """분류 결정 주체"""
    RULE = "rule"  # 정적 규칙 (블랙리스트/화이트리스트/키워드)
    LLM = "llm"    # AI 분석 (Claude Haiku)

class GmailEvent(BaseModel):
    """
    Normalized internal representation of a Gmail log event.
    """
    timestamp: datetime
    message_id: str = Field(..., description="Unique Message ID from Gmail")
    subject: Optional[str] = None
    sender: str
    recipients: List[str] = Field(default_factory=list)
    owner: str = Field(..., description="Mailbox owner email (the user who received/sent)")
    event_type: str = Field(..., description="VIEW, RECEIVE, SEND etc.")
    
    # Metadata for raw event
    raw_data: dict = Field(default_factory=dict, exclude=True)

class AnalysisResult(BaseModel):
    """
    Result of the importance classification pipeline.
    """
    score: float = Field(..., ge=0.0, le=1.0)
    category: ImportanceCategory
    reason: str
    summary: Optional[str] = Field(None, description="AI-generated 3-line summary")
    source: AnalysisSource = AnalysisSource.RULE
    raw_data: Optional[dict] = Field(default_factory=dict)

class NotificationTarget(BaseModel):
    """
    A destination for the Slack notification.
    """
    target_id: str = Field(..., description="Slack User ID (U...) or Channel ID (C...)")
    target_type: str = Field(..., description="'user' or 'channel'")
    
    def __hash__(self):
        return hash((self.target_id, self.target_type))
    
    def __eq__(self, other):
        return (self.target_id, self.target_type) == (other.target_id, other.target_type)

class ProcessedResult(BaseModel):
    """
    Final aggregation of the processing for logging/debugging.
    """
    event: GmailEvent
    analysis: AnalysisResult
    targets: List[NotificationTarget] = Field(default_factory=list)
    notification_sent: bool = False
    error: Optional[str] = None

