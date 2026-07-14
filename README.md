# md-rag-chatbot

**Markdown 노트를 소스오브트루스로 삼는 교과서적 RAG 챗봇 템플릿.**
Gemini 임베딩으로 "의미"를 찾고(Pinecone), GitHub의 `.md` 원본으로 "답"을 만듭니다(grounding).
클론 → 키 몇 개만 넣으면 바로 돌아가는 껍데기입니다.

> 핵심 원칙: **찾기(Retrieval) ≠ 답하기(Generation).**
> Pinecone = 의미로 찾는 색인. `.md` = 답의 근거가 되는 원본.

---

## ✨ 특징

- **의미 검색** — 키워드가 아니라 뜻으로 찾음. "언어모델"로 물어도 "LLM" 노트가 걸림.
- **Grounding** — 저장된 노트에 근거가 없으면 지어내지 않고 "관련 정보 없음". (임계값 abstention + 엄격 프롬프트 2중 차단)
- **Small-to-Big** — 요약을 임베딩해 깔끔하게 찾고, 답할 땐 GitHub의 원본 `.md`를 불러옴.
- **코드 vs LLM 역할 분리** — 분류·유사도·라우팅은 코드가, 요약·답변만 LLM이. (토큰 절약)
- **무상태 인증** — HMAC 서명 쿠키. 서버 재시작·서버리스 배포에도 로그인 유지.
- Next.js(App Router) + 단일 채팅 UI. Vercel 배포 지원.

---

## 🧠 동작 원리

```
[저장]  텍스트/URL → (LLM)요약·제목·태그 → GitHub에 .md 원본 기록
                                        → 요약을 임베딩해 Pinecone upsert (metadata.path = 원본 포인터)

[질문]  질문 → (Gemini)임베딩 → (Pinecone)유사도 top-k → score < 임계값 컷(abstention)
             → metadata.path 로 GitHub 원본 .md 로드 → (LLM)원본만 근거로 답변
```

누가 무엇을 하는가:

| 하는 일 | 담당 |
|---------|------|
| 텍스트 → 벡터 변환, 최종 답변 생성 | **Gemini (LLM)** |
| 유사도 검색 · 임계값 컷 · 저장/질문 분류 · 관련노트 매칭 | **코드 / Pinecone** |
| 노트 원본 저장·로드 | **코드 / GitHub** |

---

## 🚀 빠른 시작

### 요구사항
- Node.js 18+
- Gemini API 키 · Pinecone 계정 · GitHub 계정 (모두 무료 티어 가능)

### 1. 클론 & 설치
```bash
git clone https://github.com/<your-name>/md-rag-chatbot.git
cd md-rag-chatbot
npm install
```

### 2. 외부 서비스 준비

**① Gemini API 키**
[Google AI Studio](https://aistudio.google.com/apikey) → 키 발급.

**② GitHub 볼트 레포 + 토큰**
1. 노트를 저장할 repo 를 새로 만듭니다 (예: `my-knowledge-vault`, private 가능). 폴더는 자동 생성됩니다.
2. [Fine-grained 토큰](https://github.com/settings/personal-access-tokens) 발급:
   - **Repository access**: 방금 만든 볼트 repo 선택
   - **Permissions → Contents**: **Read and write**

**③ Pinecone 인덱스**
[Pinecone](https://www.pinecone.io) 가입 → 인덱스 생성. **반드시** 아래 값으로:
- **Dimensions**: `3072` (gemini-embedding-001 차원)
- **Metric**: `cosine`

### 3. 환경변수
```bash
cp .env.example .env.local
```
`.env.local` 을 열어 위에서 발급한 값들을 채웁니다. (각 항목 설명은 파일 주석 참고)

### 4. 실행
```bash
npm run dev
# http://localhost:3000 → AUTH_PASSWORD 로 로그인
```

### 5. 사용
- **저장**: URL이나 텍스트(긴 내용)를 입력 → 자동 요약 후 GitHub + Pinecone 에 저장
- **질문**: 저장한 내용에 대해 물으면 원본을 근거로 답변

### 6. (선택) 기존 노트 재색인
GitHub 볼트에 이미 노트가 있거나 임베딩 방식을 바꿨다면, 로그인 상태에서:
```js
// 브라우저 콘솔
fetch('/api/sync', { method: 'POST' }).then(r => r.json()).then(console.log)
```
→ 인덱스를 비우고 모든 노트를 다시 임베딩합니다.

---

## ☁️ 배포 (Vercel)

1. 이 repo 를 [Vercel](https://vercel.com) 에 import
2. Environment Variables 에 `.env.local` 과 동일한 값 입력
3. Deploy

> 프로덕션에서는 인증 쿠키에 `Secure` 플래그가 자동으로 붙습니다(HTTPS).

---

## 🔧 환경변수

| 변수 | 필수 | 설명 |
|------|:---:|------|
| `NEXT_PUBLIC_APP_NAME` | | 프론트에 표시할 앱 이름 (기본 `AXBrain`) |
| `GEMINI_API_KEY` | ✅ | Gemini 임베딩·생성 |
| `AUTH_PASSWORD` | ✅ | 로그인 비밀번호 (+ 서명 키) |
| `AUTH_SECRET` | | 인증 서명 전용 시크릿 (없으면 `AUTH_PASSWORD` 재사용) |
| `GITHUB_TOKEN` | ✅ | 볼트 repo Contents 읽기/쓰기 토큰 |
| `GITHUB_REPO` | ✅ | `사용자명/레포명` |
| `PINECONE_API_KEY` | ✅ | Pinecone |
| `PINECONE_INDEX` | ✅ | 인덱스 이름 (3072 dim, cosine) |

---

## ⚙️ 커스터마이즈

- **유사도 임계값**: `src/lib/pinecone.ts` 의 `THRESHOLD` (기본 `0.6`). 엉뚱한 게 답되면 ↑, 관련인데 놓치면 ↓.
- **검색 개수 top-k**: `queryNotes(question, topK)` 기본 5.
- **앱 이름**: `NEXT_PUBLIC_APP_NAME`.

---

## 📄 라이선스

MIT — 자유롭게 사용/수정/배포하세요.
