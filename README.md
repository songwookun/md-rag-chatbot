# md-rag-chatbot

A textbook RAG chatbot template that treats your Markdown notes as the source of truth.
It finds meaning with Gemini embeddings (via Pinecone) and grounds every answer in the original `.md` files on GitHub. Clone it, plug in a few keys, and it runs.

> **Core principle: Retrieval ≠ Generation.**
> Pinecone = the index that finds by meaning. `.md` = the original that answers are grounded in.

**[English](#english) · [한국어](#한국어)**

---

## Demo

<!--
  실행 영상 넣는 법 / How to add the demo video:
  1) GitHub 웹에서 이 README를 Edit 화면으로 연다 (repo → README.md → 연필 아이콘)
  2) 녹화한 .mp4 파일을 아래 이 자리에 드래그&드롭 → 자동 업로드되어
     https://github.com/user-attachments/assets/... 링크가 생성된다
  3) 아래 placeholder 줄을 그 링크로 교체
-->

> Demo video coming soon — drop your `.mp4` here in the GitHub web editor.

---

## English

### Features
- **Semantic search** — finds by meaning, not keywords. Ask about "language models" and it still surfaces your "LLM" note.
- **Grounding** — if the notes don't support an answer, it says "no relevant info" instead of making one up (threshold abstention + strict prompt, two gates).
- **Small-to-Big** — embeds the *summary* to search cleanly, then loads the full original `.md` from GitHub to answer.
- **Code vs LLM split** — classification, similarity and routing are done in code; only summarizing and answering use the LLM (saves tokens).
- **Stateless auth** — HMAC-signed cookie; stays logged in across restarts and serverless deploys.
- Next.js (App Router) + a single chat UI. Deployable on Vercel.

### How it works
```
[Save]  text/URL → (LLM) summary/title/tags → write .md original to GitHub
                                             → embed the summary → upsert to Pinecone (metadata.path = pointer to original)

[Ask]   question → (Gemini) embed → (Pinecone) top-k similarity → drop scores below threshold (abstention)
                 → load original .md from GitHub via metadata.path → (LLM) answer using the original only
```

| Task | Owner |
|------|-------|
| text → vector, final answer generation | **Gemini (LLM)** |
| similarity search, threshold cut, save/ask routing, related-note matching | **Code / Pinecone** |
| storing & loading note originals | **Code / GitHub** |

### Quick start

**Requirements:** Node.js 18+, a Gemini API key, a Pinecone account, a GitHub account (all have free tiers).

**1. Clone & install**
```bash
git clone https://github.com/<your-name>/md-rag-chatbot.git
cd md-rag-chatbot
npm install
```

**2. Set up external services**
- **Gemini API key** — get one at [Google AI Studio](https://aistudio.google.com/apikey).
- **GitHub vault repo + token**
  1. Create a new repo to store notes (e.g. `my-knowledge-vault`, can be private). Folders are created automatically.
  2. Create a [fine-grained token](https://github.com/settings/personal-access-tokens):
     - Repository access: the vault repo you just made
     - Permissions → Contents: **Read and write**
- **Pinecone index** — sign up at [Pinecone](https://www.pinecone.io) and create an index with **Dimensions: 3072** (gemini-embedding-001) and **Metric: cosine**.

**3. Environment variables**
```bash
cp .env.example .env.local
```
Open `.env.local` and fill in the values (each field is explained in the comments).

**4. Run**
```bash
npm run dev
# http://localhost:3000 → log in with AUTH_PASSWORD
```

**5. Use**
- **Save**: paste a URL or text → auto-summarized and saved to GitHub + Pinecone.
- **Ask**: ask about saved content → answered from the originals.

**6. (Optional) Re-index existing notes**
If your vault already has notes, or you changed the embedding setup, log in and run in the browser console:
```js
fetch('/api/sync', { method: 'POST' }).then(r => r.json()).then(console.log)
```
This clears the index and re-embeds every note.

### Deploy (Vercel)
1. Import this repo into [Vercel](https://vercel.com).
2. Add the same variables from `.env.local` under Environment Variables.
3. Deploy. (In production the auth cookie gets the `Secure` flag automatically over HTTPS.)

### Environment variables
| Variable | Required | Description |
|----------|:---:|-------------|
| `NEXT_PUBLIC_APP_NAME` | | App name shown in the UI (default `AXBrain`) |
| `GEMINI_API_KEY` | yes | Gemini embedding & generation |
| `AUTH_PASSWORD` | yes | Login password (also the signing key) |
| `AUTH_SECRET` | | Dedicated signing secret (falls back to `AUTH_PASSWORD`) |
| `GITHUB_TOKEN` | yes | Vault repo Contents read/write token |
| `GITHUB_REPO` | yes | `owner/repo` |
| `PINECONE_API_KEY` | yes | Pinecone |
| `PINECONE_INDEX` | yes | Index name (3072 dim, cosine) |

### Customize
- **Similarity threshold**: `THRESHOLD` in `src/lib/pinecone.ts` (default `0.6`). Raise it if junk gets answered; lower it if relevant notes get missed.
- **top-k**: `queryNotes(question, topK)`, default 5.
- **App name**: `NEXT_PUBLIC_APP_NAME`.

### License
MIT — use, modify, and distribute freely.

---

## 한국어

### 특징
- **의미 검색** — 키워드가 아니라 뜻으로 찾음. "언어모델"로 물어도 "LLM" 노트가 걸림.
- **Grounding** — 저장된 노트에 근거가 없으면 지어내지 않고 "관련 정보 없음". (임계값 abstention + 엄격 프롬프트, 2중 차단)
- **Small-to-Big** — 요약을 임베딩해 깔끔하게 찾고, 답할 땐 GitHub의 원본 `.md`를 불러옴.
- **코드 vs LLM 역할 분리** — 분류·유사도·라우팅은 코드가, 요약·답변만 LLM이. (토큰 절약)
- **무상태 인증** — HMAC 서명 쿠키. 서버 재시작·서버리스 배포에도 로그인 유지.
- Next.js(App Router) + 단일 채팅 UI. Vercel 배포 지원.

### 동작 원리
```
[저장]  텍스트/URL → (LLM)요약·제목·태그 → GitHub에 .md 원본 기록
                                        → 요약을 임베딩해 Pinecone upsert (metadata.path = 원본 포인터)

[질문]  질문 → (Gemini)임베딩 → (Pinecone)유사도 top-k → score < 임계값 컷(abstention)
             → metadata.path 로 GitHub 원본 .md 로드 → (LLM)원본만 근거로 답변
```

| 하는 일 | 담당 |
|---------|------|
| 텍스트 → 벡터 변환, 최종 답변 생성 | **Gemini (LLM)** |
| 유사도 검색 · 임계값 컷 · 저장/질문 분류 · 관련노트 매칭 | **코드 / Pinecone** |
| 노트 원본 저장·로드 | **코드 / GitHub** |

### 빠른 시작

**요구사항:** Node.js 18+, Gemini API 키, Pinecone 계정, GitHub 계정 (모두 무료 티어 가능).

**1. 클론 & 설치**
```bash
git clone https://github.com/<your-name>/md-rag-chatbot.git
cd md-rag-chatbot
npm install
```

**2. 외부 서비스 준비**
- **Gemini API 키** — [Google AI Studio](https://aistudio.google.com/apikey)에서 발급.
- **GitHub 볼트 레포 + 토큰**
  1. 노트를 저장할 repo를 새로 만듦 (예: `my-knowledge-vault`, private 가능). 폴더는 자동 생성됨.
  2. [Fine-grained 토큰](https://github.com/settings/personal-access-tokens) 발급:
     - Repository access: 방금 만든 볼트 repo
     - Permissions → Contents: **Read and write**
- **Pinecone 인덱스** — [Pinecone](https://www.pinecone.io) 가입 후 인덱스 생성. **Dimensions: 3072**(gemini-embedding-001), **Metric: cosine**.

**3. 환경변수**
```bash
cp .env.example .env.local
```
`.env.local`을 열어 발급한 값들을 채움 (각 항목 설명은 파일 주석 참고).

**4. 실행**
```bash
npm run dev
# http://localhost:3000 → AUTH_PASSWORD 로 로그인
```

**5. 사용**
- **저장**: URL이나 텍스트(긴 내용)를 입력 → 자동 요약 후 GitHub + Pinecone에 저장.
- **질문**: 저장한 내용에 대해 물으면 원본을 근거로 답변.

**6. (선택) 기존 노트 재색인**
볼트에 이미 노트가 있거나 임베딩 방식을 바꿨다면, 로그인 상태에서 브라우저 콘솔:
```js
fetch('/api/sync', { method: 'POST' }).then(r => r.json()).then(console.log)
```
→ 인덱스를 비우고 모든 노트를 다시 임베딩함.

### 배포 (Vercel)
1. 이 repo를 [Vercel](https://vercel.com)에 import.
2. Environment Variables에 `.env.local`과 동일한 값 입력.
3. Deploy. (프로덕션에선 인증 쿠키에 `Secure` 플래그가 HTTPS로 자동 적용됨.)

### 환경변수
| 변수 | 필수 | 설명 |
|------|:---:|------|
| `NEXT_PUBLIC_APP_NAME` | | 프론트에 표시할 앱 이름 (기본 `AXBrain`) |
| `GEMINI_API_KEY` | 필수 | Gemini 임베딩·생성 |
| `AUTH_PASSWORD` | 필수 | 로그인 비밀번호 (+ 서명 키) |
| `AUTH_SECRET` | | 인증 서명 전용 시크릿 (없으면 `AUTH_PASSWORD` 재사용) |
| `GITHUB_TOKEN` | 필수 | 볼트 repo Contents 읽기/쓰기 토큰 |
| `GITHUB_REPO` | 필수 | `사용자명/레포명` |
| `PINECONE_API_KEY` | 필수 | Pinecone |
| `PINECONE_INDEX` | 필수 | 인덱스 이름 (3072 dim, cosine) |

### 커스터마이즈
- **유사도 임계값**: `src/lib/pinecone.ts`의 `THRESHOLD` (기본 `0.6`). 엉뚱한 게 답되면 ↑, 관련인데 놓치면 ↓.
- **top-k**: `queryNotes(question, topK)` 기본 5.
- **앱 이름**: `NEXT_PUBLIC_APP_NAME`.

### 라이선스
MIT — 자유롭게 사용/수정/배포하세요.
