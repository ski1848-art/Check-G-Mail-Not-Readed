"""
Services 패키지 - 외부 서비스 연동 및 데이터 저장소

- gmail_service.py:    Gmail API (도메인 위임 방식으로 사용자 메일 조회)
- slack_service.py:    Slack Bot API (Block Kit 메시지 전송)
- llm_service.py:      AI 분석 (Token-Watcher 프록시 → AWS Bedrock 폴백)
- routing_store.py:    Firestore 라우팅 규칙 (Gmail→Slack 매핑, TTL 캐시)
- settings_store.py:   시스템 설정 (일시중지, 일일 한도, 사용량 추적)
- learning_store.py:   학습 데이터 (사용자 차단 목록, 이메일 스냅샷, Prior)
"""

