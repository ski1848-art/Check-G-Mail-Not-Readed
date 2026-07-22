"""
slack_service.py - Slack Bot 알림 전송 서비스

[역할]
  이메일 분석 결과를 Slack Block Kit 메시지로 전송.
  DM(개인 메시지) 또는 채널 메시지 지원.

[메시지 구조] (Block Kit)
  ┌─────────────────────────────────┐
  │ 📧 [메일 제목]                    │  ← header
  │ 보낸사람: xxx / 수신: xxx          │  ← section
  │ 📝 AI 핵심 요약                   │  ← section (optional)
  │ [Gmail 열기] [읽음 처리] [차단]     │  ← actions (interactive buttons)
  └─────────────────────────────────┘

[인터랙티브 버튼]
  - Gmail 열기: URL 버튼 (Gmail 검색 링크)
  - 읽음 처리: mark_as_read_gmail → Gmail API로 UNREAD 라벨 제거
  - 해당 유형 알림 차단: silent_forever → 학습 데이터 저장 (발신자+유형 패턴)
"""
from typing import List
import json
from datetime import datetime, timedelta, timezone
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# 한국 시간대 (KST = UTC+9)
KST = timezone(timedelta(hours=9))

def to_kst(dt: datetime) -> datetime:
    """Convert datetime to Korean Standard Time (KST)."""
    if dt.tzinfo is None:
        # naive datetime이면 UTC로 간주
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST)

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

    def send_cost_alert_dm(
        self,
        recipient_id: str,
        current_cost_usd: float,
        limit_cost_usd: float,
        threshold_percent: float,
        date_str: str,
    ) -> bool:
        """
        비용 알림 DM 전송. recipient_id는 Slack 유저 ID.
        """
        if not self.client:
            logger.warning("Slack client not initialized. Cannot send cost alert.")
            return False
        try:
            percent_used = (current_cost_usd / limit_cost_usd * 100) if limit_cost_usd > 0 else 0
            dm_response = self.client.conversations_open(users=[recipient_id])
            channel_id = dm_response["channel"]["id"]
            self.client.chat_postMessage(
                channel=channel_id,
                text=f"[비용 경고] AI 사용 비용이 한도의 {percent_used:.0f}%에 도달했습니다.",
                blocks=[
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "⚠️ AI 비용 경고", "emoji": True}
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*날짜*\n{date_str}"},
                            {"type": "mrkdwn", "text": f"*사용 비율*\n{percent_used:.1f}% (알림 기준: {threshold_percent * 100:.0f}%)"},
                            {"type": "mrkdwn", "text": f"*현재 비용*\n${current_cost_usd:.4f}"},
                            {"type": "mrkdwn", "text": f"*일일 한도*\n${limit_cost_usd:.2f}"},
                        ]
                    },
                    {
                        "type": "context",
                        "elements": [{"type": "mrkdwn", "text": "한도는 관리자 화면 → 설정에서 바꿀 수 있습니다."}]
                    }
                ]
            )
            logger.info(f"Cost alert DM sent to {recipient_id}: ${current_cost_usd:.4f}/${limit_cost_usd:.2f} ({percent_used:.1f}%)")
            return True
        except SlackApiError as e:
            logger.error(f"Failed to send cost alert DM to {recipient_id}: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending cost alert DM: {e}")
            return False

    def send_usage_spike_alert_dm(self, recipient_id: str, detail: dict) -> bool:
        """AI 사용량 급증 감지 DM. 최근 평균 대비 급증 시 즉시 통보(고정 한도와 무관)."""
        if not self.client:
            logger.warning("Slack client not initialized. Cannot send spike alert.")
            return False
        try:
            kind = detail.get("kind", "사용량 급증")
            mult = detail.get("multiplier", 0) or 0
            today_cost = detail.get("today_cost", 0.0)
            avg_cost = detail.get("avg_cost", 0.0)
            today_cpc = detail.get("today_cost_per_call", 0.0)
            recent_cpc = detail.get("recent_cost_per_call", 0.0)
            days = detail.get("sample_days", 0)
            date_str = detail.get("date", "")
            dm_response = self.client.conversations_open(users=[recipient_id])
            channel_id = dm_response["channel"]["id"]
            self.client.chat_postMessage(
                channel=channel_id,
                text=f"[급증 경고] AI 사용량이 최근 {days}일 평균 대비 급증({kind})했습니다.",
                blocks=[
                    {"type": "header", "text": {"type": "plain_text", "text": "🚨 AI 사용량 급증 감지", "emoji": True}},
                    {"type": "section", "text": {"type": "mrkdwn",
                        "text": f"*{kind}* — 최근 {days}일 평균의 *{mult:.1f}배 기준*을 넘었습니다."}},
                    {"type": "section", "fields": [
                        {"type": "mrkdwn", "text": f"*날짜*\n{date_str}"},
                        {"type": "mrkdwn", "text": f"*오늘 비용*\n${today_cost:.4f}"},
                        {"type": "mrkdwn", "text": f"*최근 평균(일)*\n${avg_cost:.4f}"},
                        {"type": "mrkdwn", "text": f"*통당 비용(오늘/평균)*\n${today_cpc:.6f} / ${recent_cpc:.6f}"},
                    ]},
                    {"type": "context", "elements": [{"type": "mrkdwn",
                        "text": "고정 한도 이하라도 평소보다 크게 늘면 알립니다. 최근 배포/설정 변경을 확인하세요."}]},
                ]
            )
            logger.info(f"Usage spike alert DM sent to {recipient_id}: {kind}, today=${today_cost:.4f}")
            return True
        except SlackApiError as e:
            logger.error(f"Failed to send spike alert DM to {recipient_id}: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending spike alert DM: {e}")
            return False

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
                    "text": f"*보낸사람*: {event.sender}\n*받는사람*: {event.owner}"
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
                            "text": "이런 알림 차단",
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
                                "text": "앞으로 비슷한 알림을 차단할까요?"
                            },
                            "text": {
                                "type": "plain_text",
                                "text": "이 발신자가 보내는 비슷한 메일만 알림이 꺼집니다. 다른 중요한 메일은 평소처럼 알림이 옵니다."
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

