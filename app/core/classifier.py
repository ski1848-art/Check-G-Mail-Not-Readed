"""
classifier.py - 이메일 중요도 분류 파이프라인

[4단계 분류 프로세스]
  Step 0-1: 규칙 기반 필터 (_apply_rules)
    - 블랙리스트 도메인 → 즉시 SILENT
    - 스팸 키워드 → 즉시 SILENT
    - 화이트리스트 도메인 → 즉시 NOTIFY (AI 요약은 별도 호출)

  Step 2: AI 분석 (LLMService.analyze_email)
    - 메일 제목/발신자/스니펫을 Claude에게 전달 (본문은 전달하지 않음)
    - 사용자별 차단 패턴(user_preferences_map)도 함께 전달
    - JSON 응답: {score, category, reason, summary, user_overrides}

  Step 3: 임계값 적용 (_apply_thresholds)
    - AI 점수가 score_threshold_notify 이상이면 NOTIFY, 미만이면 SILENT

  Step 4: 본문 기반 요약 (LLMService.summarize_email) — AI 비용 절감 핵심
    - 알림 대상(NOTIFY)으로 최종 확정된 메일만 본문을 포함해 요약을 생성
    - SILENT로 확정된 메일(다수)은 본문을 전혀 읽지 않아 LLM 비용을 절감
    - Step 0-1에서 화이트리스트로 즉시 NOTIFY 확정된 경우도 동일하게 적용

[설정 소스]
  Firestore system_settings (동적) + config/spam_filter.json (정적 기본값)
"""
from typing import Any, Dict, List, Optional
from app.models import GmailEvent, AnalysisResult, ImportanceCategory, AnalysisSource
from app.config import Config
from app.services.llm_service import LLMService
from app.utils.logger import get_logger

from app.services.settings_store import SettingsStore

logger = get_logger("classifier")

class Classifier:
    def __init__(self):
        self.llm_service = LLMService()
        self.settings_store = SettingsStore()

    def _get_filter_config(self):
        """환경변수/JSON 기반 기본값과 Firestore 설정을 결합하여 반환"""
        # 1. Firestore에서 최신 설정 가져오기
        dynamic_settings = self.settings_store.get_all_settings()
        
        # 2. 기본값 (Config 및 JSON 파일) 로드
        spam_config = Config.load_spam_filter()
        
        return {
            "blacklist_domains": dynamic_settings.get("blacklist_domains", spam_config.get("blacklist_domains", [])),
            "whitelist_domains": dynamic_settings.get("whitelist_domains", spam_config.get("whitelist_domains", [])),
            "spam_keywords": dynamic_settings.get("spam_keywords", spam_config.get("spam_keywords", [])),
            "urgent_keywords": dynamic_settings.get("urgent_keywords", spam_config.get("urgent_keywords", [])),
            "noreply_patterns": dynamic_settings.get("noreply_patterns", spam_config.get("noreply_patterns", [])),
            "score_threshold_notify": dynamic_settings.get("score_threshold_notify", Config.SCORE_THRESHOLD_NOTIFY)
        }

    def _validate_summary(self, summary: Optional[str]) -> Optional[str]:
        """요약 품질 검증: None, 빈 문자열, 공백만, 10자 미만 → None"""
        if summary is None:
            return None
        if not isinstance(summary, str):
            return None
        stripped = summary.strip()
        if not stripped or len(stripped) < 10:
            return None
        return summary

    def classify(self, event: GmailEvent, user_preferences_map: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> AnalysisResult:
        """
        Execute the 3-step classification pipeline with dynamic settings.
        """
        config = self._get_filter_config()

        # Step 0 & 1: Rule-based Filter
        rule_result = self._apply_rules(event, config)
        if rule_result:
            if rule_result.category == ImportanceCategory.NOTIFY:
                # 규칙으로 알림 대상(화이트리스트 등)인 경우 요약만 경량 호출 (전체 분류 불필요)
                logger.info(f"[{event.message_id}] RULE is NOTIFY, calling summarize_email for summary...")
                summary, usage = self.llm_service.summarize_email(event)
                rule_result.summary = self._validate_summary(summary)
                rule_result.llm_usage = usage

            logger.info(f"[{event.message_id}] Classified by RULE: {rule_result.category}")
            return rule_result

        # Step 2: LLM Analysis
        logger.info(f"[{event.message_id}] calling LLM for analysis...")
        llm_result = self.llm_service.analyze_email(event, user_preferences_map)

        # 요약 품질 검증
        llm_result.summary = self._validate_summary(llm_result.summary)

        # Step 3: Thresholding (Refine LLM result based on thresholds)
        final_result = self._apply_thresholds(llm_result, config)

        # Step 4: 알림 대상(NOTIFY)으로 확정된 메일만 본문 기반 요약 생성.
        # SILENT(무시할) 메일은 본문을 읽지 않아 비용을 절감한다.
        if final_result.category == ImportanceCategory.NOTIFY:
            logger.info(f"[{event.message_id}] NOTIFY → calling summarize_email (with body)...")
            summary, usage = self.llm_service.summarize_email(event)
            validated = self._validate_summary(summary)
            if validated:
                final_result.summary = validated
            final_result.llm_usage = self.llm_service._merge_usage(final_result.llm_usage, usage)

        logger.info(f"[{event.message_id}] Classified by LLM: {final_result.category} (Score: {final_result.score})")

        return final_result

    def _apply_rules(self, event: GmailEvent, config: Dict[str, Any]) -> Optional[AnalysisResult]:
        subject_raw = event.subject or ""
        subject = subject_raw.lower()
        sender = (event.sender or "").lower()

        # 1. Blacklist / Spam Keywords -> SILENT
        if any(d in sender for d in config["blacklist_domains"]):
            matched_domain = next(d for d in config["blacklist_domains"] if d in sender)
            return AnalysisResult(score=0.0, category=ImportanceCategory.SILENT, reason=f"차단된 발신처 (블랙리스트: {matched_domain})", source=AnalysisSource.RULE)
        
        if any(k in subject for k in config["spam_keywords"]):
            matched_keyword = next(k for k in config["spam_keywords"] if k in subject)
            return AnalysisResult(score=0.0, category=ImportanceCategory.SILENT, reason=f"광고/스팸 키워드 포함 ({matched_keyword})", source=AnalysisSource.RULE)
            
        # 2. Whitelist -> NOTIFY (공식 파트너사 등은 유지, no-reply보다 우선)
        if any(d in sender for d in config["whitelist_domains"]):
            return AnalysisResult(score=1.0, category=ImportanceCategory.NOTIFY, reason=f"공식 발신처 (화이트리스트: {sender})", source=AnalysisSource.RULE)

        # 3. no-reply 발신자 자동 SILENT
        noreply_patterns = config.get("noreply_patterns", [])
        for pattern in noreply_patterns:
            if sender.startswith(pattern) or f"<{pattern}" in sender:
                return AnalysisResult(score=0.0, category=ImportanceCategory.SILENT, reason="no-reply sender", source=AnalysisSource.RULE)

        # 키워드 기반 자동 알림(urgent_keywords)은 제거되었습니다.
        # 이제 모든 일반 메일은 LLM(AI)이 문맥을 분석하여 결정합니다.

        return None

    def _apply_thresholds(self, result: AnalysisResult, config: Dict[str, Any]) -> AnalysisResult:
        """
        Adjust category based on dynamic thresholds.
        """
        threshold = config["score_threshold_notify"]
        if result.score >= threshold:
            result.category = ImportanceCategory.NOTIFY
        else:
            result.category = ImportanceCategory.SILENT
            # AI 점수가 낮은데 사유가 없는 경우 기본 사유 채워넣기
            if not result.reason or result.reason == "사유 미기재":
                result.reason = f"AI 분석 결과 점수({result.score})가 임계치({threshold})보다 낮아 무시되었습니다."
            
        return result

