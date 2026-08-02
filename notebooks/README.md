# notebooks — 임베딩 실험실

`backend/` 코드에 박혀 있는 상수들이 근거가 있는 값인지 직접 측정한다.

## 왜 이 폴더가 있나

이 프로젝트의 TS 원본은 100% 바이브코딩으로 만들어졌다.
`src/lib/pinecone.ts:78` 에는 이런 주석이 달려 있다:

```
★ 실측 튜닝값(2026-07-14): 관련 0.64+, 무관 0.58- 사이의 골
```

**측정한 사람이 없다.** AI가 쓴 주석이다.
여기서는 그 숫자들이 맞는지 하나씩 확인한다.

## 검증 대상 (코드에 박힌 근거 불명의 주장)

| # | 주장 | 위치 | 다루는 노트북 |
|---|---|---|---|
| 1 | `task_type` 분기가 검색을 개선한다 | `src/lib/gemini.ts:19-21` | `01_task_type.ipynb` |
| 2 | 임계값 **0.6**. "관련 0.64+, 무관 0.58-" | `src/lib/pinecone.ts:78-79` | `02_threshold.ipynb` |
| 3 | **요약**을 임베딩하는 게 원본보다 낫다 | `src/lib/pinecone.ts:61` | `03_what_to_embed.ipynb` |
| 4 | 관련노트 임계값도 0.6 | `src/lib/pinecone.ts:25` | 02에서 같이 |
| 5 | `topK=5` | `src/app/api/chat/route.ts:74` | 03에서 같이 |
| 6 | 150자 이상이면 저장 의도 | `src/lib/gemini.ts:65` | 미정 |
| 7 | 의문표현 정규식이 질문을 잡는다 | `src/lib/gemini.ts:68-69` | 미정 |
| 8 | 차원 3072가 필요하다 | `.env.example` | 미정 |
| 9 | 재색인 30개 상한 (조용한 누락) | `src/lib/github.ts:84` | 실험 아님 — 버그 |

## 실행 준비

```bash
# backend 가상환경을 그대로 쓴다 (google-genai, pinecone 이미 설치됨)
cd backend
source .venv/bin/activate
pip install -e ".[lab]"

# 이 venv 를 주피터 커널로 등록
python -m ipykernel install --user --name md-rag --display-name "md-rag"

cd ../notebooks
jupyter lab
```

노트북에서 커널을 **md-rag** 로 선택할 것.

## ⚠ 실운영 데이터를 쓰고 있다

`backend/.env` 의 키는 **실제로 돌아가는 챗봇의 것**이다.

- `GITHUB_REPO` = `songwookun/my-knowledge-vault` — 진짜 노트 볼트
- `PINECONE_INDEX` = `knowledge-notes` — **앱이 지금 검색에 쓰는 인덱스**

**노트북에서 Pinecone 에 쓰기(`upsert` / `delete_all`) 를 하지 말 것.**
`delete_all` 한 번이면 돌아가는 챗봇의 검색이 죽는다.

실험은 전부 로컬에서 계산한다:
- 노트 본문 → GitHub **읽기만**
- 임베딩 → Gemini 호출 후 **메모리에 보관**
- 유사도 → `numpy` 로 직접 계산

Pinecone 쓰기가 필요한 실험(색인 방식 비교 등)을 하게 되면, 그때 **별도 인덱스**를
만들어서 `PINECONE_INDEX` 를 노트북 안에서만 덮어쓸 것.

## 규칙

1. **실패한 셀을 지우지 않는다.** 이 폴더의 목적은 결론이 아니라 과정이다.
   틀린 가설, 잘못 짠 측정, 예상과 반대로 나온 결과 — 전부 남긴다.
2. **각 노트북 마지막에 결론 셀을 쓴다.** 가설 / 결과 / 판단 / 다음 의문 4줄.
3. **커밋 전에 출력을 훑는다.** API 응답이 통째로 찍혀 키나 노트 원문이 섞일 수 있다.

## 기준 데이터 만들 때 주의 — 유사 노트

볼트를 훑어보니 제목이 거의 같은 노트가 있다:

- `concepts/2026-04-15-개발-및-아키텍처-설계-핵심-용어-정리.md`
- `concepts/2026-04-15-개발-아키텍처-설계-용어-정리.md`

그리고 `메타하네스` 내용이 `concepts/` 와 `projects/` 양쪽에 있다.

**이게 실험을 조용히 망친다.** 둘 중 하나만 정답으로 라벨링하면, 나머지 하나는
"무관 쌍"인데 점수가 높게 나온다 → 무관 최고점이 치솟고 → 실제로는 잘 작동하는데
"겹침 발생"으로 잘못 결론난다.

대응 (`pairs.jsonl` 만들 때 정할 것):
- 유사한 노트는 `relevant_paths` 에 **둘 다** 넣거나
- 그 주제로는 질문을 만들지 않거나
- 판단이 애매하면 `note` 필드에 적어두고 결과 해석 때 감안한다

## 파일

```
data/
  pairs.jsonl        질문 ↔ 정답노트 쌍 (실험 기준 데이터)
01_task_type.ipynb   실험① task_type 효과
02_threshold.ipynb   실험② 임계값 탐색      (01 이후 생성)
03_what_to_embed.ipynb 실험③ 요약 vs 원본   (02 이후 생성)
```
