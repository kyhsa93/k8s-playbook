# 안티패턴 ↔ 정석 패턴 카탈로그

각 항목은 (안티패턴, 정석 패턴, harness 검증 방법) 세 가지로 구성됩니다. harness는 가능한 한 **렌더링된 최종 K8s 오브젝트**를 기준으로 검사하도록 설계해, raw manifest / Kustomize / Helm 중 어떤 도구로 만들었는지와 무관하게 동작해야 합니다.

## 1. 워크로드 정의

| # | 안티패턴 | 정석 패턴 | harness 검증 방법 |
|---|---|---|---|
| 1 | resource requests/limits 누락 | 워크로드 특성에 맞는 requests/limits 설정 (critical=Guaranteed QoS, 일반=Burstable) | 모든 container spec에 `resources.requests`/`limits` 존재 여부 파싱 |
| 2 | 이미지 태그가 `:latest` 또는 태그 없음 | 불변 태그(semver 또는 digest)로 고정 | `image` 필드 regex로 `:latest`·태그 누락 탐지 |
| 3 | liveness/readiness probe 누락, 또는 동일 엔드포인트로 두 probe를 겸용 | startup/liveness/readiness 역할 분리, 서로 다른 엔드포인트 사용 | probe 필드 존재 여부 + 엔드포인트 동일성 비교 |
| 4 | 컨테이너를 root로 실행, `privileged: true` | `securityContext.runAsNonRoot: true` + 최소 권한 | securityContext 필드 파싱 |

## 2. 가용성 / HA

| # | 안티패턴 | 정석 패턴 | harness 검증 방법 |
|---|---|---|---|
| 5 | 크리티컬 서비스 replica=1, PodDisruptionBudget 없음 | replicas≥2 + PodDisruptionBudget 정의 | `replicas` 값, PDB 리소스 존재 여부 |
| 6 | pod anti-affinity 없어 전체 replica가 한 노드에 몰림 | `podAntiAffinity`로 노드/AZ 분산 | affinity 필드 존재 여부 |

## 3. 설정 관리

| # | 안티패턴 | 정석 패턴 | harness 검증 방법 |
|---|---|---|---|
| 7 | 환경별 값(도메인, replica 수 등)이 base manifest에 하드코딩 | Base + Overlay(Kustomize) 또는 base chart + values-per-env(Helm)로 분리 | 여러 환경 렌더링 결과를 diff해, base 자체에 환경 고유값이 박혀있는지 휴리스틱 탐지 |
| 8 | Helm values.yaml이 모든 필드를 파라미터화해 복잡도 폭발("God values file") | 실제로 환경마다 달라지는 값만 파라미터화, 나머지는 chart에 고정 | values.yaml 스키마 크기 대비 실제 환경별 오버라이드 비율 측정 |

## 4. 시크릿

| # | 안티패턴 | 정석 패턴 | harness 검증 방법 |
|---|---|---|---|
| 9 | 시크릿 값이 ConfigMap 또는 평문 env로 노출 | `Secret` 리소스 참조(`secretKeyRef`/`envFrom`) 사용 | ConfigMap/env 값에 password·token·key 등 시크릿스러운 키워드 패턴 탐지 |
| 10 | 평문 시크릿이 Git repo에 커밋됨 | Sealed Secrets/External Secrets Operator 등으로 암호화된 형태만 커밋 | Git repo 내 평문 Secret 매니페스트 존재 여부 스캔 |

## 5. 배포 / 동기화 (GitOps)

| # | 안티패턴 | 정석 패턴 | harness 검증 방법 |
|---|---|---|---|
| 11 | GitOps 컨트롤러 운용 중에 수동 `kubectl apply` 병행 | 모든 변경은 Git 커밋을 거쳐 컨트롤러가 반영, 직접 클러스터 수정 금지 | 클러스터 실제 상태 vs Git 선언 상태 diff — drift 존재 자체가 위반의 흔적 |
| 12 | 검증 게이트 없이 dev 변경이 바로 prod에 반영 | dev→staging→prod 단계별 헬스체크/테스트 통과 후 승격 (예: Kargo) | Stage 정의에 verification 조건 존재 여부 |
| 13 | 개별 애플리케이션을 하나하나 수동 등록/관리 | App of Apps(Argo CD) / Kustomization 트리(Flux)로 선언적 관리 | 루트 앱 정의 존재 여부, 하위 앱이 전부 그 트리 안에 포함되는지 |

## 6. 네임스페이스 / 테넌시

| # | 안티패턴 | 정석 패턴 | harness 검증 방법 |
|---|---|---|---|
| 14 | 모든 워크로드가 `default` 네임스페이스에 배치 | 팀/환경 단위로 네임스페이스 분리 | `namespace` 필드가 `default`인지 확인 |
| 15 | 네임스페이스 단위 RBAC 없음, 전체 클러스터 권한 부여 | 네임스페이스 스코프 Role/RoleBinding으로 최소 권한 부여 | ClusterRole(Binding) 사용 여부, 네임스페이스 스코프 RBAC 존재 여부 |

---

이 카탈로그는 최소 fixture(raw manifest)에서 harness를 먼저 구현할 때의 체크리스트로 사용하고, 이후 Kustomize/Helm/Argo CD/Flux를 fixture로 추가하면서 각 항목이 도구와 무관하게 동일하게 탐지되는지 검증합니다.
