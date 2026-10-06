# engineer 백로그 큐 — k8s-playbook

출처: business-plan `bizdev` 판정(2026-10-06, `opencore/phase1-queue.md`), 랭킹 축 G1 기여도 >
구현시간 > 선행관계. engineer는 이 파일의 **맨 위 항목 하나**만 받아 구현한다 — 우선순위를
다시 매기지 않는다. 완료되면 이 파일에서 해당 항목을 지운다(메인 세션 또는 group-cto가 확인
후 반영).

## 1. GitHub Marketplace 릴리스

- **무엇을**: `action.yml`(19개 안티패턴 하니스 전부 구현, Argo CD/Flux/Kargo 실도구 검증
  완료, LICENSE·토픽 이미 정비)은 배포 준비가 끝났지만 태그·릴리스가 0건이라 Marketplace에
  노출되지 않는다. `v0.1.0` 태그 + 릴리스 노트(19개 카탈로그 항목 완료, 실도구 검증 요약)를
  작성하고 `gh release create`로 올린다.
- **왜**: G1 기여도 상(신규 발견 채널), 구현시간 낮음(추정 1.5시간), 선행관계 없음.
- **주의**: GitHub Marketplace "Publish this Action" 체크박스는 API로 노출되는지 미확인 —
  안 되면 태그·릴리스까지만 하고 PR 본문에 "Marketplace 최종 등록은 웹 콘솔에서 사람이"라고
  적어 넘긴다.

## 2. k8s-playbook#6 — values override 주석 헤더 누락

- **무엇을**: `fixtures/config-mgmt/values-bloat/real-world/values-prod.yaml`·
  `values-staging.yaml`은 `values-dev.yaml`과 같은 패턴의 합성 override(ingress-nginx 원본을
  베낀 게 아님)인데 그 사실을 알리는 주석 헤더가 없다. `values-dev.yaml`에 있는 것과 같은
  "합성 override" 주석 헤더를 이 두 파일에 추가하면 이슈 #6이 닫힌다. README License 절
  문구는 고칠 필요 없음.
- **왜**: G1 기여도 0(순수 위생 수정), 구현시간 매우 낮음(15분), 선행관계 없음 — 순서는
  뒤지만 비용이 거의 0이라 1번과 같은 세션에서 같이 처리해도 된다.
