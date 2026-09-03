# md-rag-chatbot

> 마크다운 노트를 근거로만 답하는 개인 지식 검색 챗봇.
> **AI가 "실측 튜닝값"이라 써놓은 숫자를 직접 재보니 전부 틀렸다** — 그래서 백엔드를 다시 짰다.

<p>
<img alt="Python" src="https://img.shields.io/badge/Python_3.11+-3776AB?logo=python&logoColor=white">
<img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white">
<img alt="Next.js" src="https://img.shields.io/badge/Next.js_15-000000?logo=nextdotjs&logoColor=white">
<img alt="Gemini" src="https://img.shields.io/badge/Gemini-8E75B2?logo=googlegemini&logoColor=white">
<img alt="Pinecone" src="https://img.shields.io/badge/Pinecone-000000?logo=pinecone&logoColor=white">
<img alt="tests" src="https://img.shields.io/badge/tests-61_passing-3fb950">
</p>

**[한국어](#한국어) · [English](#english)**

---

https://github.com/user-attachments/assets/a22019a1-8686-4f04-8c58-034bc78ff6f3

---

# 한국어

## 한 줄 요약

옵시디언 마크다운 노트를 GitHub에 저장하고, 의미로 검색해서, **저장된 노트에 실제로 적힌 내용으로만** 답하는 RAG 챗봇입니다. 근거가 없으면 지어내지 않고 "모른다"고 답합니다.

## 이 프로젝트의 출발점

원본은 100% AI에게 맡겨 만든 TypeScript 코드였습니다. 그 안에 이런 주석이 있었습니다.

```ts
// ★ 실측 튜닝값(2026-07-14): 관련 0.64+, 무관 0.58- 사이의 골
const THRESHOLD = 0.6;
```

**"실측"이라고 적혀 있지만 측정한 사람이 없었습니다.** AI가 쓴 문장이었습니다.

그래서 두 가지를 했습니다.

1. **재봤습니다.** 실제 노트 20개, 질문 22개로 임베딩 설정 90여 개를 비교했습니다 → [`notebooks/`](notebooks/)
2. **다시 짰습니다.** 백엔드를 Python(FastAPI)으로 옮기면서, 코드에 박힌 모든 상수에 **근거를 달거나 근거가 없음을 명시**했습니다.

이 저장소의 핵심은 "RAG를 만들었다"가 아니라 **"내가 쓰는 숫자의 근거를 아는가"** 입니다.

---

## 동작 원리

### 저장 — 원본과 벡터를 분리한다

```
 사용자 입력 ("이 글 저장해 https://...")
      │
      ├─ ① 의도 판별          규칙 3개(URL/길이/의문표현)로 먼저 판단
      │                       규칙이 다 실패할 때만 LLM 호출  ← 대부분 API 비용 0
      │
      ├─ ② 요약               Gemini → 제목 / 요약 / 태그 / 분류
      │
      ├─ ③ 관련 노트 검색      벡터 유사도로 찾음 (LLM에게 묻지 않음)
      │                       ★ 저장 전에 호출 — 저장 후면 자기 자신을 집는다
      │
      └─ ④ 두 곳에 독립 저장
             ├── GitHub    ─  .md 원문 전체        (원본, source of truth)
             └── Pinecone  ─  요약의 임베딩만       (검색용 색인)
                              metadata.path = 원본으로 가는 포인터
```

### 질문 — 찾을 때와 답할 때 쓰는 텍스트가 다르다

```
 질문 ("메타하네스가 뭐야?")
      │
      ├─ ① 벡터 검색          질문을 임베딩 → 유사도 상위 5개
      │                       ※ 어댑터는 점수를 거르지 않고 그대로 넘긴다
      │
      ├─ ② 컷 (abstention)    0.65 미만은 근거로 쓰지 않는다
      │        │
      │        └─ 남은 게 0개 → **LLM을 아예 호출하지 않고 보류**
      │                          "관련된 내용을 찾지 못했습니다"
      │
      ├─ ③ 원본 로드           metadata.path 로 GitHub에서 .md 원문을 병렬 로드
      │                        일부 실패해도 나머지로 답한다
      │
      └─ ④ 답변 생성           원문만 컨텍스트로 넣고, 외부 지식 사용을 프롬프트로 금지
```

### 이 구조의 세 가지 축

**① Small-to-Big — 찾는 텍스트와 답하는 텍스트를 분리**

| | 쓰는 텍스트 | 이유 |
|---|---|---|
| 찾을 때 | **요약** 벡터 | 짧고 노이즈가 적어 검색이 정확하다 |
| 답할 때 | **원본** `.md` | 세부 정보가 살아 있어 답변 품질이 높다 |

둘을 잇는 것이 `metadata.path` 입니다. 벡터DB에는 본문을 저장하지 않습니다.

**② Abstention — 모르면 답하지 않는다**

유사도가 임계값에 못 미치면 **LLM을 호출조차 하지 않습니다.** 관련 없는 노트를 컨텍스트로 주면 모델은 억지로 답을 만들어냅니다. "모른다"고 말할 수 있는 것이 개인 지식 베이스의 신뢰입니다.

**③ 코드와 LLM의 역할 분리 — LLM에게 사실 판단을 맡기지 않는다**

| 하는 일 | 담당 |
|---|---|
| 요약·제목·분류, 최종 답변 생성 | **Gemini** |
| 저장/질문 판별, 유사도 계산, 임계값 컷, **관련 노트 찾기** | **코드 / Pinecone** |
| 노트 원본 저장·로드 | **코드 / GitHub** |

관련 노트를 LLM에게 물으면 **존재하지 않는 노트 제목을 그럴듯하게 지어냅니다.** 벡터 검색은 실제로 색인에 있는 것만 돌려줍니다.

---

## 측정한 것 — 코드의 숫자에는 근거가 있다

노트 20개 / 질문 22개(정답이 있는 질문 19개)로 **설정 90여 개, 임베딩 1,400여 건**을 비교했습니다.
전체 기록은 [`docs/experiments/`](docs/experiments/) 와 [`notebooks/`](notebooks/) 에 있습니다.

| 항목 | 원본 | 반영 | 근거 |
|---|---|---|---|
| 유사도 임계값 | 0.6 | **0.65** | 0.6에서는 **답이 없는 질문 3개가 전부 통과**했다. 0.65면 3개 모두 차단 (재현율 80% / 오통과율 2.2%) |
| 임베딩 차원 | 3072 | **768 권장**<br>(기본값은 3072 유지) | AUC 손실 0.001 미만에 **저장량 25%**. `gemini-embedding-001`이 MRL이라 앞쪽 차원에 정보가 몰려 있다.<br>내리려면 인덱스를 새로 만들어야 해서 기본값은 3072로 뒀다 |
| `task_type` 분기 | 있음 | **유지** | 요약 기준에서 현재 조합이 더 높다 (AUC 0.982 vs 0.972) |
| 청킹 | 없음 | **유지** | AUC +0.009를 얻는 대가가 벡터 7.5배 · 저장 3.75배 |

**90여 개를 재고 내린 결론이 "숫자 두 개만 바꾼다"인 것도 결과입니다.** 근거 없이 바꾸지 않으려고 잰 것이기 때문입니다.

### 스스로 뒤집은 결론

첫 실험에서 **분리도**(관련 평균 − 무관 평균) 하나로 판정해 "검색이 잘 안 된다"고 결론 냈습니다. 두 번째 실험에서 **AUC**로 다시 재보니 **0.982, Recall@3 = 1.00** — 상위 3개 안에 항상 정답이 있었습니다.

**검색은 원래 잘 되고 있었고, 지표 선택이 틀렸던 것입니다.** 평균의 차이는 분포의 겹침을 잡지 못합니다.

> 틀린 실험 노트를 지우지 않고 남겨두었습니다. 결론보다 **어디서 왜 틀렸는지**가 남길 가치가 있다고 판단했습니다.

---

## 아직 풀지 못한 문제

**임계값만으로는 abstention이 완성되지 않습니다.**

측정한 90여 개 설정 **전부** 아래 값이 음수였습니다.

```
보류여유 = (정답이 있는 질문의 최저 점수) − (정답이 없는 질문의 최고 점수)
최선의 설정에서도  −0.017
```

음수라는 것은 **어떤 임계값을 골라도 둘 중 하나는 반드시 틀린다**는 뜻입니다. 원인은 노트 20개가 전부 AI·개발 주제라 주제가 인접한 노트가 높게 잡히는 것입니다.

> **임베딩은 "주제가 비슷한가"를 재지, "답이 있는가"를 재지 않습니다.**

현재 0.65는 최선의 임시방편이고 해결이 아닙니다. 다음 단계는 재순위화(rerank) / 하이브리드 검색(BM25) / LLM 판정 중 무엇이 효과적인지 재는 것입니다. 그래서 컷 로직을 `_select_context()` 한 함수로 분리해 **갈아 끼울 자리를 남겨 두었습니다.**

---

## 구조

```
backend/                 Python (FastAPI) — 백엔드 전부
  app/
    api/                 HTTP 경계 — 인증 · 분기 · 예외를 문구로 변환
    services/            판단 로직 — 무엇을 저장하고, 언제 답하지 않을지
      intent.py            저장이냐 질문이냐
      ingest.py            저장 파이프라인 (부분 실패 허용)
      retrieval.py         RAG + abstention   ← 가장 중요한 파일
    adapters/            외부 서비스 경계 — GitHub / Gemini / Pinecone
    core/                공용 — HMAC 토큰 · 마크다운 조립 · 에러 문구 표
  tests/                 61개. 외부 호출 없이 전부 실행

docs/experiments/        실험 기록 — 코드의 상수들이 근거로 참조하는 문서
notebooks/               실험실 — 코드에 박힌 상수를 직접 측정
  01_task_type.ipynb       실험① task_type 분기 (결론이 뒤집힌 기록 포함)
  02_sweep.ipynb           실험② 설정 90여 개 스윕
posts/                   블로그 글 원본 (발행은 velog)

src/                     Next.js — 프론트 + 얇은 프록시 (로직 0줄)
```

### 계층 규칙 — 판단은 배관에 숨기지 않는다

원본 TypeScript는 유사도 임계값을 **검색 함수 안에서** 걸러 반환했습니다. 즉 *"얼마나 닮아야 근거로 쓸 것인가"* 라는 판단이 외부 API 호출 코드에 박혀 있었습니다.

이 구조에서는 어댑터가 점수를 그대로 돌려주고, **자르는 결정은 `services/`가 합니다.**

- 어댑터(`adapters/`) — 외부와 주고받기만 한다. 틀리면 즉시 터진다
- 서비스(`services/`) — 판단한다. **틀려도 안 터지고 조용히 이상한 답이 나온다**

그래서 서비스 계층의 판단은 전부 테스트로 고정했습니다. 예를 들어 이 테스트가 깨져도 챗봇은 정상으로 보입니다 — 다만 **저장하지 않은 내용을 지어내기 시작할 뿐입니다.**

```python
async def test_abstains_and_never_calls_llm_when_all_below_threshold():
    ...
    assert calls["answered"] == []   # ← 근거가 없으면 LLM을 부르지 않는다
```

---

## 기술 선택과 이유

| 선택 | 이유 |
|---|---|
| **FastAPI** | async 네이티브 + Pydantic 검증. 요청 형식 오류가 핸들러에 도달하기 전에 걸린다 |
| **Next.js를 얇은 프록시로 유지** | 프론트가 백엔드를 직접 부르면 CORS · `credentials` · `SameSite` 설정이 줄줄이 따라오고 **HttpOnly 쿠키 인증이 먼저 깨진다.** same-origin을 유지하는 편이 단순하다 (TS 백엔드 439줄 → 프록시 118줄) |
| **무상태 HMAC 토큰** | `만료시각.서명` 형태. 세션 저장소가 필요 없어 서버리스에서도 재시작 후 로그인이 유지된다 |
| **부분 실패 허용** | GitHub와 벡터DB는 별개 시스템이다. 하나가 죽었다고 나머지를 버리면 사용자는 아무것도 못 건진다. 어긋난 상태는 재색인(`/api/sync`)으로 복구한다 |
| **`asyncio.to_thread`로 Pinecone 감싸기** | Pinecone SDK는 동기 라이브러리라, async 핸들러에서 그냥 부르면 이벤트 루프 전체가 멈춘다 |

### 원본에서 발견해 고친 것

- **`/api/collect`가 벡터 저장을 빠뜨리고 있었습니다.** 저장 로직이 두 파일에 복사돼 있었고 한쪽만 `upsert`가 빠져서, 외부 도구(iOS 단축어)로 넣은 노트는 **GitHub에는 있는데 검색이 되지 않았습니다.** 한 함수로 합치니 구조적으로 사라졌습니다.
- **재색인이 30개를 넘는 노트를 조용히 버리고 있었습니다.** 상한에 걸리면 경고를 남기도록 바꿨습니다.
- **재색인 안전장치.** 노트를 0개 읽어왔을 때 그것이 "노트가 없는 것"인지 "GitHub 읽기 실패"인지 구분할 수 없습니다. 구분이 안 되면 인덱스를 비우지 않습니다 — 그렇지 않으면 GitHub이 잠깐 죽은 날 재색인 한 번에 검색이 통째로 사라집니다.

---

<details>
<summary><b>실행 방법</b></summary>

> **API 키는 이 저장소에 포함돼 있지 않습니다.** (`.env.example` 에 빈 칸만 있습니다)
> 클론한 뒤 아래 세 서비스에서 **본인 키를 직접 발급**받아 `backend/.env` 에 채워야 합니다.
> 셋 다 무료 티어로 충분합니다. 노트도 본인 GitHub 저장소에 쌓이므로, 이 저장소 소유자는
> 다른 사람의 노트나 사용량에 관여하지 않습니다.

**필요한 것:** Python 3.11+, Node.js 18+ · 아래 3개 서비스 계정 (전부 무료 티어)

| 서비스 | 무엇에 쓰나 | 무료 티어 |
|---|---|---|
| [Gemini API](https://aistudio.google.com/apikey) | 임베딩 + 답변 생성 | 있음 (분당 요청 제한) |
| [Pinecone](https://www.pinecone.io) | 벡터 검색 | 있음 (인덱스 1개) |
| [GitHub](https://github.com/settings/personal-access-tokens) | 노트 원본 저장 | 무료 (private repo 가능) |

**1. 백엔드**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env      # 키 채우기
uvicorn app.main:app --reload --port 8000
```
확인: `curl localhost:8000/health` · API 문서: `http://localhost:8000/docs`

**2. 프론트엔드** (다른 터미널)
```bash
npm install
cp .env.example .env.local   # BACKEND_URL 기본값 http://localhost:8000
npm run dev
```
`http://localhost:3000` → `AUTH_PASSWORD`로 로그인

**3. 외부 서비스 준비**
- **Gemini** — [Google AI Studio](https://aistudio.google.com/apikey)에서 키 발급
- **GitHub 볼트** — 노트 저장용 repo 생성(private 가능) + [fine-grained 토큰](https://github.com/settings/personal-access-tokens) (Contents: Read and write)
- **Pinecone** — 인덱스 생성. **Dimensions: 3072**(또는 768) / **Metric: cosine**

**4. 기존 노트 재색인** (선택)
```bash
curl -b cookie.txt -X POST localhost:3000/api/sync
```

**환경변수**

| 변수 | 위치 | 필수 | 설명 |
|---|---|:---:|---|
| `GEMINI_API_KEY` | backend | ✓ | 임베딩 + 생성 |
| `GITHUB_TOKEN` / `GITHUB_REPO` | backend | ✓ | 볼트 repo (`owner/repo`) |
| `PINECONE_API_KEY` / `PINECONE_INDEX` | backend | ✓ | 벡터 DB |
| `AUTH_PASSWORD` | backend | ✓ | 로그인 비밀번호 (서명 키 겸용) |
| `AUTH_SECRET` | backend | | 서명 전용 시크릿 (없으면 `AUTH_PASSWORD` 재사용) |
| `EMBEDDING_DIMENSIONS` | backend | | 기본 3072. 인덱스 차원과 반드시 일치 |
| `BACKEND_URL` | frontend | | 기본 `http://localhost:8000` |

**튜닝**
- 유사도 임계값: `backend/app/services/retrieval.py`의 `SCORE_THRESHOLD` (기본 `0.65` — 실측값)
- 후보 개수: 같은 파일의 `TOP_K` (기본 5)

**배포 주의** — 프론트(Next)와 백엔드(FastAPI)를 각각 호스팅해야 합니다. 프론트만 Vercel에 올리면 `BACKEND_URL`이 가리킬 곳이 필요합니다.

</details>

---

## 라이선스

MIT

---

# English

## What it is

A personal knowledge chatbot that stores Markdown notes on GitHub, searches them by meaning, and answers **only from what the notes actually say**. If the evidence isn't there, it says so instead of making something up.

## Why I rebuilt it

The original was written entirely by AI, in TypeScript. It contained this comment:

```ts
// ★ Measured tuning values (2026-07-14): relevant 0.64+, irrelevant 0.58-
const THRESHOLD = 0.6;
```

**Nobody had measured anything.** The AI wrote that sentence.

So I did two things: I **measured** (20 real notes, 22 questions, 90+ embedding configurations — see [`notebooks/`](notebooks/)), and I **rewrote** the backend in Python, giving every constant either evidence or an explicit note that it has none.

The point of this repo isn't "I built a RAG app." It's **"do I know why the numbers in my code are what they are?"**

## How it works

```
[Save]  input → intent (3 code rules first, LLM only if all fail)
              → summarize (Gemini)
              → find related notes by vector similarity  ★ before upsert, or it matches itself
              → GitHub: full .md original     ┐ independent —
                Pinecone: embedding of the summary only, metadata.path → pointer to original

[Ask]   question → embed → top-k similarity (adapter does NOT filter)
                 → cut below 0.65 → if nothing remains, **never call the LLM**, abstain
                 → load original .md from GitHub via metadata.path (partial failure tolerated)
                 → answer from originals only, external knowledge forbidden by prompt
```

**Three principles**

- **Small-to-Big** — search on the *summary* vector (clean, low noise), answer from the *full original* (detail survives). `metadata.path` is the link. No note bodies in the vector DB.
- **Abstention** — below threshold, the LLM is never invoked. Giving a model irrelevant context makes it invent answers. Being able to say "I don't know" is what makes a personal knowledge base trustworthy.
- **Code vs LLM** — the LLM summarizes and writes the final answer. Classification, similarity, thresholds and **related-note lookup** are code. Ask an LLM for related notes and it will confidently invent titles that don't exist.

## What I measured

| | Original | Now | Evidence |
|---|---|---|---|
| Similarity threshold | 0.6 | **0.65** | At 0.6, **all 3 unanswerable questions passed through**. At 0.65 all 3 are blocked (recall 80% / false-pass 2.2%) |
| Embedding dimensions | 3072 | **768 recommended**<br>(default still 3072) | AUC loss < 0.001, **75% less storage** (`gemini-embedding-001` is Matryoshka). Lowering it requires recreating the index, so the default stays 3072 |
| `task_type` split | on | **kept** | On summaries the current pair scores higher (AUC 0.982 vs 0.972) |
| Chunking | none | **kept** | +0.009 AUC costs 7.5× vectors, 3.75× storage |

Full records: [`docs/experiments/`](docs/experiments/) and [`notebooks/`](notebooks/).

**Measuring 90+ configurations and concluding "change two numbers" is itself the result** — the point was to avoid changing anything without evidence.

**I overturned my own conclusion.** My first experiment judged retrieval by *mean separation* alone and called it poor. Re-measured with AUC: **0.982, Recall@3 = 1.00**. Retrieval was fine all along; the metric was wrong. Means don't capture distribution overlap. The failed notebook is kept, not deleted.

## What's still unsolved

Every one of the 90+ configurations produced a **negative** value for:

```
abstention margin = (lowest score among answerable questions)
                  − (highest score among unanswerable questions)
best case: −0.017
```

Negative means **no threshold can be correct for both cases.** The cause: all 20 notes are about AI/development, so topically adjacent notes score high.

> **Embeddings measure "is this topically similar", not "does this contain the answer."**

0.65 is the best available stopgap, not a solution. Next step is measuring rerankers vs hybrid (BM25) vs LLM judging — which is why the cut lives in one isolated `_select_context()` function, ready to be swapped.

## Architecture notes

- **Judgment doesn't hide in plumbing.** The original TS filtered by threshold *inside the search function* — the decision "how similar is similar enough" was buried in API-call code. Here adapters return raw scores and `services/` decides. Adapters fail loudly; services fail *silently*, so every service-layer judgment is pinned by a test.
- **Next.js stays as a thin proxy** (439 lines of TS backend → 118 lines of proxy). Calling the Python backend directly from the browser breaks same-origin, and HttpOnly cookie auth is the first casualty.
- **Partial failure is allowed.** GitHub and the vector DB are separate systems; if one dies the other still saves, and `/api/sync` reconciles them.
- **Bugs found in the original**: `/api/collect` never wrote to the vector DB (duplicated save logic that drifted), so notes added via iOS Shortcuts were invisible to search; re-indexing silently dropped notes past 30.

**Running it yourself** — no API keys are included in this repo (`.env.example` ships empty). You bring your own Gemini key, Pinecone index, and GitHub vault repo + token; all three have free tiers, and your notes live in your own repository. See the Korean section's collapsed setup guide.

61 tests, all runnable without network access.

MIT License.
