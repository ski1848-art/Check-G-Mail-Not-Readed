# 목적 중심 완료 프레임워크 (IOV)

모든 작업은 **Intent(목적) → Outcome(기대결과) → Verification(검증)**으로 판단. 파일 수정 ≠ 완료.

## Gate 1: Definition of Ready (작업 시작 전)
| 요소 | 질문 | 예시 |
|------|------|------|
| **WHY** | 근본 목적은? | "이중관리 제거 — 단일 뷰로 통합" |
| **OUTCOME** | 완료 시 관찰 가능한 변화? | "서브탭 없이 단일 목록, 결의+이체 구분 불필요" |
| **VERIFY** | 어떻게 확인? | "DB 쿼리 + UI 확인 + tsc" |

- Trivial(1-2파일, 1-5줄): WHY만 확인
- Standard 이상: 3요소 전부 필수. 누락 시 사용자에게 1줄 확인

## Gate 2: Definition of Done (완료 판정)
기존 리뷰 체인(tsc → test-runner → parallel-reviewer) **이후** 추가:
1. **AC Check**: Gate 1의 OUTCOME이 실제로 달성되었는가? (API 호출, DB 쿼리, UI 확인 등 실행 검증)
2. **Side Effect Check**: 의도하지 않은 곳에 영향 없는가? (수정 함수의 다른 호출처 확인)
3. **메인 직접 검증 필수**: 워커/에이전트 보고를 맹신 금지 — **메인(Opus 1M)이 핵심 파일을 직접 Read하여 사실 확인 후** 완료 판정. 워커 보고 요약만으로 완료 선언 금지.
4. **UI 변경 시 시각적 검증 필수**: tsc만으로 UI 완료 선언 금지 — **Playwright 스크린샷 또는 사용자 확인**으로 실제 화면 검증. 코드만 보고 "개선됨" 판단 금지.
5. **OUTCOME 보고**: `OUTCOME_MET` / `OUTCOME_PARTIAL` / `OUTCOME_NOT_MET` 필수 명시

`OUTCOME_NOT_MET` 시 완료 보고 금지 — 미달성 사유 + 추가 작업 명시.
