---
inclusion: always
---

# 기술 스택 및 개발 규칙

## 백엔드 (Python)
- Python 3.11+, Flask 3.x, Gunicorn
- Pydantic v2 (데이터 모델 검증)
- google-api-python-client (Gmail API)
- slack_sdk (Slack 알림)
- anthropic / boto3 (AWS Bedrock LLM)
- google-cloud-firestore (DB)
- python-dotenv (환경변수)

## 프론트엔드 (admin-web)
- Next.js (App Router), TypeScript
- Tailwind CSS
- admin-web/ 하위에서 독립적으로 동작

## 인프라
- Google Cloud Run (백엔드 컨테이너)
- Cloud Scheduler → `/run-batch` (5분 주기)
- Firestore (NoSQL DB)
- AWS Bedrock (LLM)

## 코드 작성 규칙
1. 모든 함수에 Python 타입 힌트 필수
2. 민감 정보는 반드시 환경변수(`os.environ`)로만 접근, 하드코딩 금지
3. 개별 메일 처리 실패가 전체 배치 실패로 이어지지 않도록 try-except 처리
4. 로그는 JSON 포맷 지향 (Cloud Run 호환), 필수 필드: `messageId`, `owner`, `score`, `level`
5. 동일 `messageId` + `Slack Target` 조합에 중복 알림 금지 (멱등성)
6. 응답은 항상 한국어로
7. 사용자가 명시적으로 개발 요청을 하기 전까지 코드 수정/추가를 하지 않는다. 문제 분석 및 원인 파악만 하고 보고한다.

## 환경변수 목록
| 변수 | 설명 |
|---|---|
| `SLACK_BOT_TOKEN` | Slack Bot OAuth 토큰 |
| `SLACK_SIGNING_SECRET` | Slack 서명 검증 시크릿 |
| `AWS_ACCESS_KEY_ID` | AWS 자격증명 |
| `AWS_SECRET_ACCESS_KEY` | AWS 자격증명 |
| `AWS_REGION` | AWS 리전 (기본: us-east-1) |
| `BEDROCK_MODEL_ID` | Bedrock 모델 ARN |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP 서비스 계정 키 경로 |
| `FIRESTORE_PROJECT_ID` | Firestore 프로젝트 ID |
| `ROUTING_SOURCE` | `firestore` 또는 `json` |
| `INTERNAL_AUTH_TOKEN` | 내부 API 인증 토큰 |
| `CORS_ALLOWED_ORIGINS` | CORS 허용 오리진 |

## Feature Flags (기본 OFF)
| 플래그 | 설명 |
|---|---|
| `FEATURE_SLACK_SIGNATURE_VERIFY` | Slack 서명 검증 활성화 |
| `FEATURE_REQUIRE_INTERNAL_TOKEN` | 내부 API 토큰 인증 활성화 |
| `FEATURE_ENFORCE_LIMITS_DURING_BATCH` | 배치 중 사용량 한도 체크 |
| `FEATURE_GMAIL_PAGINATION` | Gmail 페이지네이션 활성화 |
