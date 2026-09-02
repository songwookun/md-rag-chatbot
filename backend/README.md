# backend — Python(FastAPI) 엔진

TS 백엔드(`src/lib`, `src/app/api`)를 Python으로 이관하는 작업 공간.
프론트(`src/components`, `src/app/page.tsx`)는 건드리지 않는다.

## 실행

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env      # 값 채우기
uvicorn app.main:app --reload --port 8000
```

확인:

```bash
curl localhost:8000/health          # {"status":"ok", ...}
open http://localhost:8000/docs     # 자동 생성 API 문서
```

## 진행 상황

- [x] 0단계 — 폴더 뼈대 + `config.py`
- [x] 1단계 — `/health` + 환경변수 로딩
- [x] 2단계 — `core/security.py` (HMAC 토큰) + `api/auth.py` + `api/deps.py`
- [x] 3단계 — `adapters/` 3개 + `core/markdown.py` + `core/errors.py`
- [ ] 4단계 — `services/intent.py`, `services/ingest.py`   ← **직접 구현**
- [ ] 5단계 — `services/retrieval.py`                      ← **직접 구현**
- [ ] 6단계 — `api/chat.py` 통합
- [ ] 7단계 — `sync` / `collect`
- [ ] 8단계 — 프론트 프록시 전환

### 작업 분담

| | 누가 | 왜 |
|---|---|---|
| `adapters/` `core/` `api/` 배선 | AI | 틀리면 즉시 터진다 → 검증 비용 0 |
| `services/` | **직접** | 틀려도 안 터진다. 조용히 이상한 답이 나올 뿐 |

`services/` 3개 파일은 `raise NotImplementedError` 상태이고, 각 함수 docstring 에
**계약(입출력) + 판단할 것 + 관련 실험 번호**만 적혀 있다. 단계별 정답은 일부러 없다.

상세 설계는 `../docs/code_design.md`.

## 읽는 순서 (구현 전 파악용)

1. `app/config.py` — 설정이 어떻게 들어오는지
2. `app/main.py` — 라우터가 어떻게 붙는지
3. `app/schemas/chat.py` — 주고받는 데이터 모양
4. `app/core/markdown.py` — 노트 .md 형식 (순수 함수, 제일 읽기 쉽다)
5. `app/adapters/` — 외부 서비스 경계. **어댑터는 점수를 거르지 않는다**
6. `app/services/` — 판단 로직 (직접 구현할 부분)

## 실험 결과가 코드에 들어간 곳

| 값 | 위치 | 근거 |
|---|---|---|
| 임계값 `0.65` | `services/retrieval.py` | 실험② — 0.6 에서는 답 없는 질문 3개가 전부 통과했다 |
| 차원 `3072` (유지) | `config.py` `EMBEDDING_DIMENSIONS` | 실험②는 768 을 권하지만 **현재 인덱스가 3072** 라 새 인덱스가 필요하다 |
| `task_type` 분기 (유지) | `adapters/gemini.py` | 실험② — 요약 기준에서는 현재 조합이 더 높다 |

`src/lib/pinecone.ts:78` 의 `★ 실측 튜닝값` 주석은 **측정한 사람이 없었다.**
파이썬 쪽에는 실제로 잰 값만, 근거 링크와 함께 옮겼다.

## 아직 확인 못 한 것

`/health` 와 인증 엔드포인트는 실제로 띄워서 확인했다.
`adapters/gemini.py` `adapters/pinecone.py` 는 **실제 API 를 호출해본 적이 없다** —
6단계에서 `api/chat.py` 가 붙어야 처음 불린다. SDK 응답 모양이 다르면 그때 드러난다.
