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

    def get_last_llm_usage(self) -> Optional[Dict[str, int]]:
        """마지막 LLM 호출의 토큰 사용량 반환"""
        return self.llm_service.last_usage

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
            "score_threshold_notify": dynamic_settings.get("score_threshold_notify", Config.SCORE_THRESHOLD_NOTIFY)
        }

    def classify(self, event: GmailEvent, user_preferences_map: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> AnalysisResult:
        """
        Execute the 3-step classification pipeline with dynamic settings.
        """
        config = self._get_filter_config()
        
        # Step 0 & 1: Rule-based Filter
        rule_result = self._apply_rules(event, config)
        if rule_result:
            if rule_result.category == ImportanceCategory.NOTIFY:
                # 규칙으로 알림 대상(화이트리스트 등)인 경우에도 요약을 위해 AI 호출
                logger.info(f"[{event.message_id}] RULE is NOTIFY, calling LLM for summary...")
                llm_result = self.llm_service.analyze_email(event, user_preferences_map)
                rule_result.summary = llm_result.summary
            
            logger.info(f"[{event.message_id}] Classified by RULE: {rule_result.category}")
            return rule_result
            
        # Step 2: LLM Analysis
        logger.info(f"[{event.message_id}] calling LLM for analysis...")
        llm_result = self.llm_service.analyze_email(event, user_preferences_map)
        
        # Step 3: Thresholding (Refine LLM result based on thresholds)
        final_result = self._apply_thresholds(llm_result, config)
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
            
        # 2. Whitelist -> NOTIFY (공식 파트너사 등은 유지)
        if any(d in sender for d in config["whitelist_domains"]):
            return AnalysisResult(score=1.0, category=ImportanceCategory.NOTIFY, reason=f"공식 발신처 (화이트리스트: {sender})", source=AnalysisSource.RULE)

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

