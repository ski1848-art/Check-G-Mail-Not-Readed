from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

class ImportanceCategory(str, Enum):
    NOTIFY = "notify"
    SILENT = "silent"

class AnalysisSource(str, Enum):
    RULE = "rule"  # Determined by static rules
    LLM = "llm"    # Determined by LLM

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

