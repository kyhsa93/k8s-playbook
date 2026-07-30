# k8s-playbook

Kubernetes 배포 구성에서 반복적으로 나타나는 **안티패턴을 정의하고 자동으로 잡아내는** 것이 이 repo의 목적입니다.

## 원칙

이 repo의 핵심 산출물은 **안티패턴 카탈로그 + 그것을 탐지하는 harness**입니다. raw manifest / Kustomize / Helm, 혹은 Argo CD / Flux 같은 도구 비교는 목적이 아니라, harness가 특정 도구의 출력 형태에 우연히 맞춰진 게 아니라 실제로 일반적인 규칙인지 검증하기 위한 fixture로만 사용합니다.

- 먼저 [안티패턴 카탈로그](docs/catalog.md)를 정의하고, 각 안티패턴과 짝을 이루는 정석 패턴을 함께 기록합니다.
- 최소 구성(raw manifest 하나)으로 harness를 먼저 만들고 검증합니다.
- 그 다음에야 Kustomize/Helm, Argo CD/Flux 등을 fixture로 추가해 harness가 도구에 종속되지 않는지 확인합니다.

## 현재 상태

- [x] 안티패턴 ↔ 정석 패턴 카탈로그 초안 ([docs/catalog.md](docs/catalog.md))
- [ ] 최소 fixture(raw manifest) + 렌더링-후 검사 harness
- [ ] Kustomize/Helm fixture 추가, harness 일반성 검증
- [ ] GitOps 상태 검사(드리프트, 승격 게이트) harness
- [ ] Argo CD/Flux fixture 추가, harness 일반성 검증
