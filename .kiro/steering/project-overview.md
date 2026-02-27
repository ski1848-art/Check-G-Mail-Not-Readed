---
inclusion: always
---

# 프로젝트 개요: Gmail Important Mail Notifier

## 목적
Google Workspace 계정의 미확인 중요 메일을 감지하여 Slack으로 알림을 보내는 서비스.
비즈니스 중요 메일(투자, 장애, 주요 고객 등)을 놓치지 않게 하고, 불필요한 알림은 최소화한다.

## 아키텍처 요약
- **백엔드**: Python 3.11+ / Flask / Google Cloud Run
- **트리거**: Cloud Scheduler (HTTP POST, 5분 주기) → `/run-batch`
- **프론트엔드**: Next.js (admin-web) — 관리자 대시보드
- **DB**: Google Cloud Firestore (라우팅 규칙, 이메일 이벤트 스냅샷, 설정, 학습 데이터)
- **LLM**: AWS Bedrock (Claude Haiku) — 메일 중요도 판별 및 요약
- **알림**: Slack Bot (slack_sdk)

## 디렉토리 구조
```
/
├── app/                    # Python 백엔드 (Flask)
│   ├── main.py             # Flask 앱, 엔드포인트 정의
│   ├── config.py           # 환경변수 및 설정 로더
│   ├── models.py           # Pydantic 데이터 모델
│   ├── core/
│   │   ├── classifier.py   # 메일 중요도 분류 파이프라인
│   │   └── router.py       # Slack 알림 대상 결정
│   ├── services/
│   │   ├── gmail_service.py    # Gmail API (미확인 메일 조회)
│   │   ├── llm_service.py      # AWS Bedrock LLM 호출
│   │   ├── slack_service.py    # Slack 메시지 전송
│   │   ├── routing_store.py    # Firestore 라우팅 규칙 조회
│   │   ├── settings_store.py   # Firestore 시스템 설정 관리
│   │   └── learning_store.py   # Firestore 학습 데이터 관리
│   └── utils/
│       ├── logger.py           # JSON 구조화 로깅
│       └── state_store.py      # 중복 알림 방지 상태 관리
├── admin-web/              # Next.js 관리자 대시보드
│   └── app/
│       ├── api/            # Next.js API Routes (백엔드 프록시)
│       ├── audit/          # 감사 로그 페이지
│       ├── events/         # 이메일 이벤트 목록 페이지
│       ├── settings/       # 시스템 설정 페이지
│       └── users/          # 사용자/라우팅 관리 페이지
├── config/
│   ├── routing_rules.json  # JSON 기반 라우팅 규칙 (fallback)
│   └── spam_filter.json    # 스팸/화이트리스트 규칙
├── Dockerfile              # Cloud Run 배포용
└── deploy.sh               # 배포 스크립트
```

## 주요 엔드포인트
| 엔드포인트 | 메서드 | 설명 |
|---|---|---|
| `/health` | GET | 헬스체크 |
| `/run-batch` | POST | 배치 실행 (Cloud Scheduler 트리거) |
| `/trigger-notification` | POST | 수동 알림 전송 |
| `/block-notification` | POST | 수동 알림 차단 |
| `/slack/interactive` | POST | Slack 버튼 인터랙션 처리 |
