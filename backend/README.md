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
- [ ] 2단계 — `core/security.py` (HMAC 토큰)
- [ ] 3단계 — `adapters/` 3개
- [ ] 4단계 — `services/ingest.py`
- [ ] 5단계 — `services/retrieval.py`
- [ ] 6단계 — `api/chat.py` 통합
- [ ] 7단계 — `sync` / `collect`
- [ ] 8단계 — 프론트 프록시 전환

상세 설계는 `../docs/code_design.md`.

## 읽는 순서 (구현 전 파악용)

1. `app/config.py` — 설정이 어떻게 들어오는지
2. `app/main.py` — 라우터가 어떻게 붙는지
3. `app/schemas/` — 주고받는 데이터 모양
4. `app/adapters/` — 외부 서비스 경계
5. `app/services/` — 판단 로직 (직접 구현할 부분)
