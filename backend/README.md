# backend — Python(FastAPI) 엔진

TS 백엔드(`src/lib`, `src/app/api`)를 Python으로 이관한 결과. **이관은 끝났다.**
프론트(`src/components`, `src/app/page.tsx`)는 한 줄도 건드리지 않았고,
`src/app/api/*` 는 여기로 요청을 넘기는 얇은 프록시만 남았다.

## 실행

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Python 3.11+
pip install -e ".[dev]"
cp .env.example .env      # 값 채우기
uvicorn app.main:app --reload --port 8000
```

확인:

```bash
curl localhost:8000/health          # {"status":"ok", ...}
open http://localhost:8000/docs     # 자동 생성 API 문서
pytest -q                           # 61 passed
```

프론트까지 같이 띄우려면 저장소 루트에서 `npm run dev` (`:3000` → `:8000` 프록시).

## 진행 상황

- [x] 0단계 — 폴더 뼈대 + `config.py`
- [x] 1단계 — `/health` + 환경변수 로딩
- [x] 2단계 — `core/security.py` (HMAC 토큰) + `api/auth.py` + `api/deps.py`
- [x] 3단계 — `adapters/` 3개 + `core/markdown.py` + `core/errors.py`
- [x] 4단계 — `services/intent.py`, `services/ingest.py`
- [x] 5단계 — `services/retrieval.py`
- [x] 6단계 — `api/chat.py` 통합
- [x] 7단계 — `api/sync.py` / `api/collect.py`
- [x] 8단계 — 프론트 프록시 전환 (`src/lib/proxy.ts`, TS 백엔드 439줄 삭제)

**8단계 전부 완료.** 다음은 코드가 아니라 실험③(abstention 구조 개선)이다.

### 작업 분담

| | 누가 | 왜 |
|---|---|---|
| `adapters/` `core/` `api/` 배선 | AI | 틀리면 즉시 터진다 → 검증 비용 0 |
| `services/` | **직접** | 틀려도 안 터진다. 조용히 이상한 답이 나올 뿐 |

`services/` 3개 파일은 **계약(입출력) + 정한 것 + 관련 실험 번호**를 파일 최상단에
남겨두는 형식으로 썼다. 구현 전에는 "판단할 것"으로, 구현 후에는 "정한 것"으로 바뀐다 —
**무엇을 정했는지보다 왜 그렇게 정했는지가 6개월 뒤에 필요하기 때문**이다.

상세 설계는 `../docs/code_design.md`.

## 읽는 순서 (구현 전 파악용)

1. `app/config.py` — 설정이 어떻게 들어오는지
2. `app/main.py` — 라우터가 어떻게 붙는지
3. `app/schemas/chat.py` — 주고받는 데이터 모양
4. `app/core/markdown.py` — 노트 .md 형식 (순수 함수, 제일 읽기 쉽다)
5. `app/adapters/` — 외부 서비스 경계. **어댑터는 점수를 거르지 않는다**
6. `app/services/` — 판단 로직. `retrieval.py` 가 이 저장소에서 가장 중요한 파일이다

## 실험 결과가 코드에 들어간 곳

| 값 | 위치 | 근거 |
|---|---|---|
| 임계값 `0.65` | `services/retrieval.py` `SCORE_THRESHOLD` | [실험② 결정 3](../docs/experiments/02-sweep.md) — 0.6 에서는 답 없는 질문 3개가 전부 통과했다 |
| 차원 `3072` (유지) | `config.py` `EMBEDDING_DIMENSIONS` | [실험② 결정 2](../docs/experiments/02-sweep.md) — 768 을 권하지만 **현재 인덱스가 3072** 라 새 인덱스가 필요하다 |
| `task_type` 분기 (유지) | `adapters/gemini.py` `embed()` | [실험② 결정 4](../docs/experiments/02-sweep.md) — 요약 기준에서는 현재 조합이 더 높다 |

`src/lib/pinecone.ts:78` 의 `★ 실측 튜닝값` 주석은 **측정한 사람이 없었다.**

> 코드 곳곳의 `TS 원본:` / `TS 대응:` 주석이 가리키는 `src/lib/*.ts` 는
> 커밋 `8289f4a` 이후 삭제됐다(이관이 끝나 죽은 코드가 됐다).
> `git show 8289f4a:src/lib/gemini.ts` 로 볼 수 있다.
파이썬 쪽에는 실제로 잰 값만, 근거 링크와 함께 옮겼다.

## 엔드포인트

| | 인증 | 용도 |
|---|---|---|
| `POST /api/auth` · `GET /api/auth/check` | — | 로그인 / 상태 확인 |
| `POST /api/chat` | 쿠키 | 저장 또는 질문 (프론트가 쓰는 유일한 경로) |
| `POST /api/sync` | 쿠키 | 전체 재색인 |
| `POST /api/collect` | `Authorization: Bearer` | 외부 도구(iOS 단축어) 수집 |

`http://localhost:8000/docs` 에서 전부 확인 가능.

## 검증 상태

| | 방법 |
|---|---|
| 서비스 계층 판단 | 테스트 61개. 어댑터를 전부 가짜로 갈아끼워 네트워크 없이 돈다 |
| 인증 · 라우팅 · 401/422 | 서버를 띄워 실제 요청으로 확인 |
| 프록시(쿠키·헤더 전달) | `:3000` → `:8000` 왕복으로 확인 |
| **외부 SDK 계약** | **실제 Gemini · Pinecone · GitHub 호출로 확인** (2026-09-02) |

마지막 항목이 오래 비어 있었다. 테스트 61개는 전부 어댑터를 모킹한 것이라
SDK 응답 모양이 다르면 잡아내지 못한다. 실제로 불러서 저장 → 색인 → 검색 →
원본 로드 → 답변 왕복이 도는 것까지 확인했다.

abstention 이 두 관문으로 나뉘어 동작하는 것도 실측으로 확인됐다.

| 질문 | 최고 유사도 | 막은 곳 | 걸린 시간 |
|---|---|---|---|
| 김치찌개 끓이는 법 | 0.589 — 컷 미달 | **코드** (LLM 호출 0회) | 1.7초 |
| BM25 하이브리드 검색 | 0.655 — 컷 통과 | **프롬프트** (LLM이 "노트에 없다") | 4.3초 |

앞은 결정론적 **보장**이고, 뒤는 모델이 지시를 따라준 **부탁**이다.
이 차이가 `docs/experiments/02-sweep.md` 의 "보류여유 음수" 결론이
실제 동작으로 나타난 형태다.

## 직접 확인하려면

```bash
uvicorn app.main:app --reload --port 8000

# 로그인해서 쿠키를 받은 뒤 — 질문 모드는 읽기만 한다 (Pinecone 에 쓰지 않음)
curl -b cookie.txt localhost:8000/api/chat \
  -H 'Content-Type: application/json' -d '{"message":"메타하네스가 뭐야?"}'
```

> 저장 모드(`URL 또는 150자 이상`)는 **GitHub 에 커밋하고 Pinecone 에 upsert 한다.**
> 실볼트를 쓰고 있다면 되돌리려면 양쪽을 다 지워야 한다.
