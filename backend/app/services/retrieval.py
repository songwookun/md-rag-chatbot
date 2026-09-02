"""RAG 검색 → 답변 파이프라인.

TS 원본: src/app/api/chat/route.ts:72-129

이 프로젝트에서 가장 중요한 파일이다. "언제 답하지 않을 것인가"를 정하는 곳.


흐름
────────────────────────────────────────────────────────────────
    질문
     → pinecone.query           벡터 유사도 top_k. ★ 점수가 안 걸러진 채로 온다
     → _select_context          여기서 자른다 (abstention 의 실체)
     → (남은 게 0개면 보류)     ★ 지어내지 않는다
     → github.get_content       path 로 원본 .md 병렬 로드 (small-to-big)
     → (하나도 못 읽으면 보류)
     → gemini.answer_from_notes 원본을 근거로 생성


왜 이 구조인가
────────────────────────────────────────────────────────────────
① small-to-big — '찾을 때'와 '답할 때' 쓰는 텍스트가 다르다.
   찾기   요약 벡터 (짧고 노이즈 적어 검색이 정확하다)
   답하기 원본 .md (세부 정보가 살아있어 답변 품질이 높다)
   둘을 잇는 게 NoteHit.path 다. 벡터DB에는 본문이 없다.

② abstention — 근거가 약하면 LLM 을 **아예 부르지 않는다.**
   관련 없는 노트를 컨텍스트로 주면 모델은 억지로 답을 만들어낸다.
   "모른다"고 말할 수 있는 것이 이 RAG 의 신뢰다.

③ 부분 실패 허용 — 5개 중 2개 로드에 실패해도 나머지 3개로 답한다.
   전부 실패했을 때만 포기한다.


정한 것
────────────────────────────────────────────────────────────────
① 컷은 서비스가 한다 (어댑터가 아니라)
   TS 는 pinecone.ts:79 에서 걸러 반환했다. 즉 "얼마나 닮아야 근거로 쓸 것인가"라는
   판단이 검색 배관에 숨어 있었다. 여기로 올려서 눈에 보이게 한다.

② 임계값을 넘은 건 **전부** 컨텍스트에 넣는다 (상위 N 으로 더 자르지 않는다)
   컷을 통과했다는 건 이미 근거로 쓸 만하다는 뜻이다. 여기서 또 자르면
   기준이 두 개가 되어 6개월 뒤에 어느 쪽이 진짜 기준인지 알 수 없어진다.
   노트 20개 규모에서 토큰 걱정은 이르다. 노트가 늘면 그때 재본다.
   ※ pinecone 은 점수 내림차순으로 돌려준다. 순서를 따로 만들지 않는다.

③ path 가 빈 hit 는 버린다
   metadata 가 통째로 없는 옛 벡터가 있을 수 있다(adapters/pinecone.py 참고).
   path 가 없으면 원본을 못 읽으므로 근거가 될 수 없다.

④ "못 찾음"과 "못 읽음"을 다른 문구로 알린다
   사용자 입장에서 원인이 다르다 — 노트에 그 내용이 없는 것 vs GitHub 이 죽은 것.
   같은 문구로 뭉치면 "저장했는데 왜 없다고 하지?" 하고 헤매게 된다.

⑤ 답변에 근거 노트 목록을 따로 붙이지 않는다
   프롬프트(gemini.answer_from_notes)가 이미 [[노트이름]] 표기를 요구하고 있다.
   여기서 또 붙이면 같은 정보가 두 번 나온다.

⑥ 원본 로드는 병렬 + 개별 실패 허용
   asyncio.gather 기본 동작은 하나가 터지면 나머지를 취소한다.
   return_exceptions=True 가 없으면 ③(부분 실패 허용)이 조용히 깨진다.


★ 아직 해결 안 된 문제 — 임계값으로는 못 고친다
────────────────────────────────────────────────────────────────
실험②에서 측정한 90여 설정이 **전부** 보류여유가 음수였다.
    보류여유 = (정답 있는 질문의 최저 점수) − (정답 없는 질문의 최고 점수)
음수라는 건 어떤 임계값을 골라도 둘 중 하나는 반드시 틀린다는 뜻이다.

원인은 볼트 20개가 전부 AI/개발 주제라 주제가 인접한 노트가 높게 잡히는 것.
**임베딩은 "주제가 비슷한가"를 재지 "답이 있는가"를 재지 않는다.**

그래서 SCORE_THRESHOLD 는 최선의 임시방편이지 해결이 아니다.
구조를 바꿔야 하고 후보는 재순위화 / 하이브리드 검색(BM25) / LLM 판정이다.
→ 실험③에서 무엇이 효과적인지 재고 나서 **_select_context 안에** 끼워 넣는다.
   그 함수가 한 줄짜리인데도 따로 있는 이유가 이것이다. 갈아끼울 자리.


검증
────────────────────────────────────────────────────────────────
tests/test_retrieval.py — 어댑터를 monkeypatch 로 갈아끼워 네트워크 없이 돈다.
가장 중요한 테스트는 "근거가 없으면 LLM 을 부르지 않는다"이다.
"""

import asyncio
import logging

from app.adapters import gemini, github, pinecone
from app.schemas.chat import LoadedNote, NoteHit

log = logging.getLogger(__name__)

# 검색해올 후보 수. 늘리면 회수율↑ 컨텍스트 길이↑ 비용↑
# ※ 근거 없는 값 — notebooks/README.md 검증대상 #5.
#   실험②에서 R@3 = 1.00 이 나왔으니 5는 여유 있는 쪽이다.
TOP_K = 5

# ★ 이 파일에서 가장 비싼 한 줄.
#   실험②(docs/notion/02_sweep_study.md 결정 3):
#     0.6  — 답이 볼트에 없는 질문 3개가 **전부 통과**했다 (0.686 / 0.655 / 0.639)
#     0.65 — 3개 모두 차단. 그때 재현율 80%, 오통과율 2.2%
#   정답의 20%를 놓치는 대가로, 없는 답을 지어내는 걸 막는 값이다.
SCORE_THRESHOLD = 0.65

# 보류 문구 (TS: chat/route.ts:87-89, 115)
NO_MATCH_MESSAGE = (
    "저장된 노트 중 이 질문과 관련된 내용을 찾지 못했습니다. "
    "(지어내지 않고 답변을 보류합니다)"
)
LOAD_FAILED_MESSAGE = "관련 노트를 찾았지만 원본을 불러오지 못했습니다."


def _select_context(hits: list[NoteHit]) -> list[NoteHit]:
    """검색 결과 중 답변 근거로 쓸 것만 고른다. abstention 이 실제로 일어나는 곳."""
    # path 가 없으면 원본을 못 읽으므로 근거가 될 수 없다 (정한 것 ③)
    return [h for h in hits if h.score >= SCORE_THRESHOLD and h.path]


async def _load_notes(hits: list[NoteHit]) -> list[LoadedNote]:
    """근거로 고른 노트들의 원본 .md 를 병렬 로드. 실패한 건 빼고 돌려준다."""
    # ★ return_exceptions 가 없으면 하나 실패에 전체가 취소된다 (정한 것 ⑥)
    results = await asyncio.gather(
        *(github.get_content(h.path) for h in hits),
        return_exceptions=True,
    )

    notes = []
    # zip 으로 짝지어야 어떤 hit 의 결과인지 안 잃는다 — 실패가 섞이면 인덱스가 밀린다
    for hit, result in zip(hits, results):
        if isinstance(result, BaseException):
            # 전부 실패했을 때 원인을 알 수 있어야 한다
            log.warning("원본 로드 실패, 건너뜁니다: %s (%s)", hit.path, result)
            continue
        notes.append(LoadedNote(name=hit.title, content=result))
    return notes


async def answer(question: str) -> str:
    """질문에 답한다. 근거가 없으면 지어내지 않고 보류 문구를 돌려준다."""

    # 검색 실패는 예외로 올린다 — api 층이 Pinecone 안내 문구로 바꾼다
    hits = await pinecone.query(question, TOP_K)

    context_hits = _select_context(hits)
    if not context_hits:
        # ★ 여기서 "최고점 하나만이라도 넣어줄까" 하는 유혹을 참는 게 핵심이다.
        #   그 순간 이건 RAG 가 아니라 그냥 챗봇이 된다. LLM 을 부르지 않는다.
        return NO_MATCH_MESSAGE

    notes = await _load_notes(context_hits)
    if not notes:
        # 찾긴 찾았는데 못 읽은 것 — 위와 원인이 다르므로 문구를 나눈다 (정한 것 ④)
        return LOAD_FAILED_MESSAGE

    return await gemini.answer_from_notes(question, notes)
