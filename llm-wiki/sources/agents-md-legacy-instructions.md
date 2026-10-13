---
title: 삭제된 AI 작업 규칙 (AGENTS.md 레거시 지침)
type: source
updated: 2026-10-02
sources: [git show 01f2f64:AGENTS.md]
verified: false
---

## 요약

NamiFAX로의 PHP 이식 작업이 진행 중이던 2024-2026년에 AI에게 요구하던 역할과 작업 규칙. 레거시 시스템(PHP)을 타깃 언어(Python/Pyramid)로 재설계하는 "수석 소프트웨어 아키텍트" 역할, 4단계 포팅 프로세스(Phase 1~4), 엄격한 가드레일 6가지를 정의했으며, 이식이 완료되어 2026-10-02 커밋 4400287에서 삭제됨.

## 핵심 내용

### 역할과 정체성 (**이식 완료로 모두 더 이상 적용 안 됨**)
- 역할: 레거시 시스템을 타깃 언어로 재설계 및 이식하는 "수석 소프트웨어 아키텍트(Full-System Legacy Porting Architect)"
- 원칙 1: 단순한 코드 번역이 아닌 재설계
- 원칙 2: **계약에 의한 설계(Design by Contract)** 및 **교목형 패턴(Strangler Fig Pattern)** 기반
- 원칙 3: 프로젝트 디렉터리 구조를 엄격히 준수

### 디렉터리 구조 (**현재는 일부 삭제됨**)
당시 표준 구조:
```
avantfax/
├── AGENTS.md                   # [삭제됨] AI 전역 행동 지침
├── ARCHITECTURE.md             # [삭제됨] 커밋 01f2f64
├── prompts/                    # [삭제됨] Phase 1~4 워크플로우 프롬프트 (커밋 72a7324)
├── golden_master/              # [삭제됨] E2E 검증 데이터 (커밋 72a7324)
├── specs/                      # [삭제됨] 모듈 명세서 (커밋 72a7324)
├── legacy/                     # [삭제됨] 원본 PHP 소스 (커밋 9408385)
└── src/                        # [유지됨] 신규 Python/Pyramid 소스
```

### 4가지 핵심 운영 원칙 (**이식 완료로 더 이상 적용 안 됨**)

1. **Spec-First Pipeline (명세 우선 원칙) - 더 이상 적용 안 함**
   - 소스 코드는 '구현 방식(How)'일 뿐. 비즈니스 로직과 제약 조건('What/Why')을 먼저 명세화 후 테스트 → 코드 작성
   - 단 한 줄의 코드도 명세와 테스트 없이 작성 금지
   - **현재**: 이식 완료. 신규 기능 추가 시만 적용

2. **Bottom-Up Migration (하위 모듈 우선 이식) - 더 이상 적용 안 함**
   - 의존성 그래프(DAG)상 리프 모듈부터 역순 이식
   - 상위 모듈 이식 전, 이식된 하위 모듈은 FFI/gRPC 등으로 레거시와 브리지 유지
   - **현재**: 전체 이식 완료됨

3. **Zero Regression & Continuous Verification (회귀 방지) - 일부 적용 중**
   - 레거시 예외 동작, 경계값, 버그 회피 로직까지 명세에 반영
   - 모듈 1개 교체마다 E2E Golden Master 테스트 수행
   - **현재**: 이식 완료되었지만, 기존 기능 유지를 위해 테스트는 계속 중요

4. **UI Fidelity & Modern Tailwind CSS - 완료됨**
   - 레거시 PHP 템플릿을 Pyramid + Jinja2로 이식
   - Tailwind CSS로 현대화하되 레거시 화면 일치
   - 웹 라우트별 Golden Master 검증
   - **현재**: 이식 완료. HTML/CSS 유지보수만 진행

### 4단계 포팅 프로세스 (**모두 완료되어 더 이상 적용 안 됨**)

**Phase 1: Architecture Scanning & DAG Generation - 완료**
- 소스 코드 분석해 백엔드 의존성 및 웹 라우트/템플릿 아키텍처 파악
- `ARCHITECTURE.md` 작성/업데이트 (현재 삭제됨)

**Phase 2: E2E Golden Master Test Suite - 완료**
- CLI 시스템 및 웹 프런트엔드 Golden Master 데이터 추출
- E2E 차분 테스트 스크립트 작성 (현재 `dev/` 삭제됨)

**Phase 3: Unit Module & Web UI Porting Loop - 완료**
- `[명세 추출] ➔ [단위/골든 테스트 작성] ➔ [Pyramid 뷰 + Tailwind CSS 작성] ➔ [통합 검증]`의 단계 순차 진행
- 모든 모듈과 뷰 이식 완료

**Phase 4: Entry Point Cutover & Cleanup - 완료**
- 최상위 진입점 전환, Tailwind 빌드 파이프라인 통합
- Dead Code 정리, 최종 E2E 검증

### 엄격한 가드레일 6가지 (**이식 완료로 더 이상 적용 안 됨**)

1. **🚫 No Line-by-Line Translation - 준수되어 완료**
   - C/C++ 포인터 연산이나 PHP 구조를 직역 금지
   - Python/Pyramid의 idiomatic 패턴 적용 (타입 힌트, Pydantic, SQLAlchemy, Jinja2)
   - **현재**: 이식 완료되었으므로 더 이상 적용 대상 아님

2. **🚫 No Visual/Style Degradation - 준수되어 완료**
   - 레거시 UI를 단순화하거나 텍스트 나열로 축소 금지
   - Tailwind CSS로 레거시 화면 충실히 재현
   - **현재**: 완료됨

3. **🚫 No Broken Route/Form Contracts - 준수되어 완료**
   - 레거시 PHP 라우트의 파라미터, 유효성 검증, 권한 분기 빠짐없이 수용
   - **현재**: 완료됨

4. **🚫 No Unconfirmed Assumptions - 준수되어 완료**
   - 모호한 의도나 비즈니스 제약을 `[NEEDS_CLARIFICATION]` 태그로 질문
   - **현재**: 이식 완료되었으므로 새로운 기능에만 적용

5. **🚫 No Scope Creep - 준수됨**
   - 한 대화에 2개 이상의 모듈/뷰 동시 이식 금지
   - 1개 모듈 테스트 통과 후 다음 진행
   - **현재**: 이식 완료로 더 이상 적용 안 함

6. **🧹 Dead Code Removal Protocol - 준수됨**
   - 사용되지 않는 로직(Dead Code)을 발견하면 이식 대상에서 제외
   - `ARCHITECTURE.md`에 '제거된 로직' 기록 (현재 문서 삭제됨)
   - **현재**: 완료됨

### `ARCHITECTURE.md` 관리 규칙 (**문서 삭제로 더 이상 적용 안 됨**)
- 시스템의 단일 진실 공급원(SSOT)이자 AI 세션 간 상태 공유 메모리
- 필수 구성: 시스템 개요, 의존성 DAG, 공유 데이터 모델, 포팅 상태 행렬
- 상태값: `[PENDING]`, `[IN_PROGRESS]`, `[FFI_BRIDGED]`, `[COMPLETE]`
- **현재**: 커밋 4400287에서 삭제됨. llm-wiki로 지식 이전 중

## 문서가 주장하는 수치·상태

- **삭제 시점**: 2026-10-02, 커밋 4400287
- **원본 보관 위치**: 커밋 01f2f64
- **디렉터리 정리 이력**:
  - `dev/` (golden_master, specs, prompts): 커밋 72a7324 삭제
  - `legacy/` (원본 PHP 소스): 커밋 083920e 삭제
  - `ARCHITECTURE.md`, `AGENTS.md`: 커밋 4400287 삭제

## 낡았을 가능성이 큰 부분

- **Phase 1~4 프로세스**: 이식 완료로 더 이상 적용되지 않으므로 현재 신규 개발에는 맞지 않음
- **Golden Master 위치**: `dev/` 디렉터리 삭제로 현재 저장소에서 직접 접근 불가(git 이력에서만 복원 가능)
- **ARCHITECTURE.md 참조**: 다른 문서에서 이를 "17장" 등으로 가리키지만 현재 삭제됨(커밋 01f2f64에서 복원 필요)
- **명세 및 프롬프트**: `prompts/` 디렉터리 삭제로 이식 과정 추적 불가
- **가드레일의 현재 적용성**: 모든 가드레일이 "이식 완료로 더 이상 적용 안 함"이므로, 신규 기능 개발에는 이 규칙을 그대로 적용하면 안 됨

## 관련 주제 페이지

[[architecture-and-modules]] [[testing]] [[known-gaps-and-decisions]]
