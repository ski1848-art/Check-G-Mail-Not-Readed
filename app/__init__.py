"""
Gmail Important Mail Notifier - 메인 애플리케이션 패키지

[프로젝트 개요]
Gmail에서 수신된 이메일을 AI(Claude Haiku)가 분석하여
중요한 메일만 Slack으로 알림을 보내주는 서비스.

[아키텍처]
- 백엔드: Flask (Python) → Cloud Run 배포
- 프론트엔드: Next.js 14 (admin-web/) → 관리자 대시보드
- DB: Google Firestore (라우팅 규칙, 이메일 이벤트, 사용자 피드백 등)
- AI: AWS Bedrock (Claude Haiku 4.5) 또는 Token-Watcher 프록시
- 알림: Slack Bot (DM/채널 메시지)

[핵심 흐름]
1. Cloud Scheduler가 5분마다 /run-batch POST 호출
2. GmailService가 등록된 사용자들의 미읽은 메일을 Gmail API로 가져옴
3. Classifier가 규칙 기반 필터 → AI 분석 순서로 중요도 판별
4. Router가 메일 수신자 → Slack 알림 대상자 매핑
5. SlackService가 Block Kit 메시지로 알림 전송
6. 사용자가 Slack에서 "알림 차단" 버튼 클릭 시 학습 데이터 저장

[패키지 구조]
app/
├── main.py          - Flask 앱, API 엔드포인트 (배치 실행, Slack 인터랙션)
├── config.py        - 환경변수 및 JSON 설정 로더
├── models.py        - Pydantic 데이터 모델 (GmailEvent, AnalysisResult 등)
├── core/
│   ├── classifier.py - 이메일 중요도 분류 파이프라인 (규칙 + AI)
│   └── router.py     - 이메일 → Slack 알림 대상 라우팅
├── services/
│   ├── gmail_service.py    - Gmail API 연동 (메일 조회, 읽음 처리)
│   ├── slack_service.py    - Slack Bot 알림 전송
│   ├── llm_service.py      - AI(Claude) 호출 및 응답 파싱
│   ├── routing_store.py    - Firestore 라우팅 규칙 캐시
│   ├── settings_store.py   - 시스템 설정/제어 (일시중지, 일일한도)
│   └── learning_store.py   - 학습 데이터 저장 (사용자 피드백, Prior)
└── utils/
    ├── logger.py      - Cloud Run용 구조화 로깅
    └── state_store.py - 중복 알림 방지 상태 관리 (File/Firestore)
"""

