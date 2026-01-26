from typing import List
import json
from datetime import datetime, timedelta, timezone
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import ssl
import urllib3
from urllib3.util.ssl_ import create_urllib3_context

# 한국 시간대 (KST = UTC+9)
KST = timezone(timedelta(hours=9))

def to_kst(dt: datetime) -> datetime:
    """Convert datetime to Korean Standard Time (KST)."""
    if dt.tzinfo is None:
        # naive datetime이면 UTC로 간주
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)

# SSL 인증서 검증 무시 (로컬 환경용, 프로덕션에서는 제거)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# SSL context 생성 및 검증 비활성화
def get_ssl_context():
    ctx = create_urllib3_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

from app.config import Config
from app.models import NotificationTarget, GmailEvent, AnalysisResult
from app.utils.logger import get_logger

logger = get_logger("slack_service")

class SlackService:
    def __init__(self):
        self.token = Config.SLACK_BOT_TOKEN
        if self.token:
            # Cloud Run 환경에서는 SSL 검증이 정상 작동
            self.client = WebClient(token=self.token)
            logger.info("Slack WebClient initialized successfully")
        else:
            self.client = None
            logger.warning("SLACK_BOT_TOKEN is not set. Notifications will be skipped.")

    def send_notification(
        self,
        targets: List[NotificationTarget],
        event: GmailEvent,
        analysis: AnalysisResult
    ) -> bool:
        """
        Send notification to multiple Slack targets (users/channels).
        Returns True if all notifications succeed.
        """
        if not self.client:
            logger.warning(f"Slack client not initialized. Skipping notification for {event.message_id}")
            return False

        blocks = self._build_blocks(event, analysis)
        fallback_text = self._build_fallback_text(event, analysis)
        all_success = True

        for target in targets:
            try:
                if target.target_type == "channel":
                    # Channel message
                    self.client.chat_postMessage(
                        channel=target.target_id,
                        text=fallback_text,
                        blocks=blocks,
                        unfurl_links=False
                    )
                    logger.info(f"Sent notification to channel: {target.target_id}")
                    
                elif target.target_type == "user":
                    # DM to user
                    # Open a DM channel first
                    dm_response = self.client.conversations_open(users=[target.target_id])
                    channel_id = dm_response["channel"]["id"]
                    
                    self.client.chat_postMessage(
                        channel=channel_id,
                        text=fallback_text,
                        blocks=blocks,
                        unfurl_links=False
                    )
                    logger.info(f"Sent DM to user: {target.target_id}")
                    
            except SlackApiError as e:
                logger.error(f"Failed to send notification to {target.target_id}: {e.response['error']}")
                all_success = False
            except Exception as e:
                logger.error(f"Unexpected error sending to {target.target_id}: {e}")
                all_success = False

        return all_success

    def _build_fallback_text(self, event: GmailEvent, analysis: AnalysisResult) -> str:
        """
        Build fallback text for notifications that don't support blocks.
        """
        category_text = {
            "notify": "알림",
            "silent": "무시"
        }
        
        category_display = category_text.get(analysis.category.value, "알림")
        return f"[{category_display}] {event.subject or '(제목 없음)'}"
    
    def _build_blocks(
        self,
        event: GmailEvent,
        analysis: AnalysisResult
    ) -> list:
        """
        Build Slack Block Kit message blocks with interactive buttons.
        Simplified design for business users - minimal emoji, clear information hierarchy.
        """
        # Category display mapping
        category_text = {
            "notify": "알림 필요",
            "silent": "알림 불필요"
        }
        category_display = category_text.get(analysis.category.value, "알림")
        
        # Source display mapping (한글화)
        source_text = {
            "rule": "자동 규칙",
            "llm": "AI 분석"
        }
        source_display = source_text.get(analysis.source.value, "시스템")
        
        recipients_str = ", ".join(event.recipients) if event.recipients else event.owner
        
        # Gmail link
        gmail_link = f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{event.message_id}"
        
        # Header text
        header_text = event.subject or "(제목 없음)"
        if len(header_text) > 150:
            header_text = header_text[:147] + "..."
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📧 {header_text}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*보낸사람*: {event.sender}\n*수신*: {event.owner}"
                }
            },
        ]

        # Add AI Summary if available
        if analysis.summary:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📝 *AI 핵심 요약*\n{analysis.summary}"
                }
            })

        blocks.extend([
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Gmail 열기",
                            "emoji": False
                        },
                        "style": "primary",
                        "url": gmail_link,
                        "action_id": "open_gmail"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "읽음 처리",
                            "emoji": False
                        },
                        "value": json.dumps({
                            "message_id": event.message_id,
                            "owner": event.owner
                        }),
                        "action_id": "mark_as_read_gmail"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "해당 유형 알림 차단",
                            "emoji": False
                        },
                        "style": "danger",
                        "value": json.dumps({
                            "message_id": event.message_id,
                            "sender": event.sender,
                            "subject": event.subject
                        }),
                        "action_id": "silent_forever",
                        "confirm": {
                            "title": {
                                "type": "plain_text",
                                "text": "특정 유형 알림 차단"
                            },
                            "text": {
                                "type": "plain_text",
                                "text": "이 발신자가 보내는 비슷한 유형의 메일 알림만 꺼집니다. 내용이 다른 중요한 메일은 평소처럼 정상적으로 알림이 옵니다."
                            },
                            "confirm": {
                                "type": "plain_text",
                                "text": "차단"
                            },
                            "deny": {
                                "type": "plain_text",
                                "text": "취소"
                            }
                        }
                    }
                ]
            }
        ])
        
        return blocks

    def _build_message(self, event: GmailEvent, analysis: AnalysisResult) -> str:
        """
        Build legacy Slack message text (for backward compatibility).
        Used in dry-run mode.
        """
        category_text = {
            "notify": "알림 필요",
            "silent": "알림 불필요"
        }
        
        source_text = {
            "rule": "자동 규칙",
            "llm": "AI 분석"
        }
        
        category_display = category_text.get(analysis.category.value, "알림")
        source_display = source_text.get(analysis.source.value, "시스템")
        
        recipients_str = ", ".join(event.recipients) if event.recipients else event.owner
        
        message = f"""[{category_display}] 메일 감지
        
보낸사람: {event.sender}
제목: {event.subject or '(제목 없음)'}
받는사람: {recipients_str}

분류: {category_display} ({source_display})
이유: {analysis.reason}
시간: {to_kst(event.timestamp).strftime('%Y-%m-%d %H:%M:%S')} KST
"""
        return message

