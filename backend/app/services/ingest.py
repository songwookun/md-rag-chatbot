"""저장 파이프라인 — 사용자 입력을 노트로 만들어 GitHub + Pinecone 에 넣는다.

TS 원본: src/app/api/chat/route.ts:131-244


흐름
────────────────────────────────────────────────────────────────
    입력
     → gemini.summarize          제목/요약/태그/분류
     → pinecone.find_related     관련 노트  ★ upsert 전에! (self-match 방지)
     → markdown.build_note       .md 본문 조립
     → github.save               ┐ 서로 독립. 하나 실패해도
     → pinecone.upsert_note      ┘ 다른 하나는 진행
     → IngestResult


설계 원칙 — 부분 실패 허용
────────────────────────────────────────────────────────────────
GitHub 저장과 벡터 저장은 별개 시스템이다. 하나가 죽었다고 나머지를 버리면
사용자는 아무것도 못 건진다. 각각 따로 시도하고, 무엇이 됐고 무엇이 안 됐는지
결과에 담아 돌려준다. (TS: chat/route.ts:226-234 의 4가지 분기)

대가로 두 저장소가 어긋난 상태가 생길 수 있다 → 그걸 고치는 게 sync(재색인)다.

★ 그래서 이 함수는 예외를 두 가지로 나눠 다룬다.
    요약 실패    → 예외를 그대로 올린다. 제목도 본문도 없어서 더 진행할 수 없다.
    저장 실패    → 예외를 삼키고 결과에 담는다. 나머지 한쪽은 살릴 수 있다.


재사용 — api/chat.py 와 api/collect.py 가 같은 함수를 부른다
────────────────────────────────────────────────────────────────
TS 는 이 로직이 두 파일에 복사돼 있었고, collect 쪽만 Pinecone upsert 가
빠져 있었다(collect/route.ts:67-78). 그래서 iOS 단축어로 넣은 노트는
검색이 안 되고 sync 를 돌려야 잡혔다. 한 함수로 만들면 그 버그가 구조적으로 사라진다.


정한 것
────────────────────────────────────────────────────────────────
① 관련 노트는 **요약**으로 찾는다 (원문 아님)
   TS 와 같다(chat/route.ts:148). 원문으로 찾으면 결과가 달라진다 —
   실험②가 "무엇을 임베딩하느냐에 따라 최적이 뒤집힌다"고 보여준 그 문제다.

② find_related 는 반드시 upsert_note **앞**에서 부른다
   뒤에 부르면 방금 넣은 노트가 자기 자신을 관련 노트로 집는다(self-match).
   순서가 곧 정확성인 드문 경우라, 리팩터 시 제일 먼저 깨진다.

③ 관련 노트 검색 실패는 저장을 멈추지 않는다
   [[링크]]는 부가 기능이고 노트 본문은 이미 만들어져 있다.
   ★ 단, 이 실패를 vector.error 에 담지 않는다. "검색이 안 됐다"와
     "저장이 안 됐다"는 다른 사건이고, 섞으면 saved=True 인데 error 도 찬
     모순 상태가 만들어진다. related_lookup_failed 로 따로 둔다.

④ 두 저장은 순차로 한다
   독립적이라 asyncio.gather 로 묶으면 빠르다. 다만 gather 는 하나가 터지면
   나머지를 취소한다 — 그러면 부분 실패 허용이 조용히 깨진다.
   바꾸려면 return_exceptions=True 가 필요하고, tests/test_ingest.py 의
   부분 실패 테스트가 그 리팩터를 지켜준다. 지금은 동작하는 코드부터.

⑤ 벡터에는 **요약**을 넣는다 (small-to-big)
   원본은 GitHub 에 있으니 벡터DB에 본문을 중복 저장할 이유가 없다.
   metadata.path 가 원본으로 가는 포인터 역할을 한다.
   (실험②: 요약 기준이 현재 설정에서 더 높았다)

⑥ 경로는 "category/파일명.md" 다
   ★ category 가 곧 폴더명이다(articles/concepts/projects).
     빼먹으면 노트가 레포 **루트**에 저장된다. 아무것도 안 터지고 저장도 되지만,
     github.list_notes() 가 저 세 폴더만 훑기 때문에 **재색인에 영영 안 잡힌다.**
     벡터DB를 비우고 sync 를 돌리는 순간 그 노트들만 조용히 사라진다.

⑦ 같은 날 같은 제목이 또 오면 그대로 실패시킨다
   GitHub 이 422 를 준다. 이름에 -2 를 붙여 재시도할 수도 있지만,
   대부분 실수로 두 번 보낸 경우라 조용히 두 개 만드는 것보다 알려주는 게 낫다.


검증
────────────────────────────────────────────────────────────────
tests/test_ingest.py — 어댑터 셋을 monkeypatch 로 갈아끼우면 네트워크 없이
부분 실패 4분기를 전부 테스트할 수 있다. 그게 이 함수의 핵심이다.
"""

import logging
from dataclasses import dataclass, field

from app.adapters import gemini, github, pinecone
from app.core import errors, markdown

log = logging.getLogger(__name__)

# 관련 노트로 [[링크]]를 걸 최소 유사도.
# ★ retrieval.SCORE_THRESHOLD(0.65) 와 같은 값일 이유가 없다.
#   답변 근거는 틀리면 거짓말이 되지만, 관련 노트 링크는 틀려도 어색한 정도다.
#   TS 원본은 둘 다 0.6 이었다 — 판단이었는지 복사였는지 알 수 없다.
RELATED_THRESHOLD = 0.6

# 관련 노트로 붙일 최대 개수. TS: pinecone.ts findRelatedNotes(topK=3)
RELATED_TOP_K = 3


@dataclass
class SaveOutcome:
    """한 저장소에 대한 시도 결과.

    ok 와 error 를 한 객체로 묶은 이유 — 따로 두면 "ok=True 인데 error 도 있는"
    상태가 표현 가능해진다. 유효하지 않은 상태를 아예 못 만들게 하는 쪽이,
    만들지 않도록 주의하는 쪽보다 낫다.
    """

    ok: bool = False
    error: str = ""


@dataclass
class IngestResult:
    """저장 시도 결과. api/chat.py 가 이걸 사용자 메시지로 바꾼다.

    ★ 서비스는 '무슨 일이 있었는지'만 반환하고, 문장 만들기는 api 층의 몫이다.
      이렇게 나눠야 서비스 로직을 UI 문구와 무관하게 테스트할 수 있다.
    """

    title: str = ""
    summary: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)

    github: SaveOutcome = field(default_factory=SaveOutcome)
    vector: SaveOutcome = field(default_factory=SaveOutcome)

    # 관련 노트 **검색** 실패. 저장 실패와 다른 사건이라 따로 둔다. (정한 것 ③)
    related_lookup_failed: bool = False


async def ingest(message: str) -> IngestResult:
    """입력을 노트로 만들어 두 저장소에 넣고, 부분 성공을 담아 반환한다."""

    # 요약 실패는 올려보낸다 — 제목도 본문도 없어서 더 진행할 수 없다
    summary = await gemini.summarize(message)

    result = IngestResult(
        title=summary.title,
        summary=summary.summary,
        category=summary.category,
        tags=list(summary.tags),
    )

    # ★ upsert 전에 호출. 뒤면 방금 넣은 노트가 자기 자신을 집는다 (정한 것 ②)
    try:
        hits = await pinecone.find_related(result.summary, top_k=RELATED_TOP_K)
        # 어댑터는 점수를 안 거른다 — 자를 기준을 정하는 게 이 층의 몫이다
        result.related = [h.title for h in hits if h.score >= RELATED_THRESHOLD and h.title]
    except Exception as exc:
        # [[링크]]는 부가 기능 — 저장은 계속한다. 저장 실패와 섞지 않는다 (정한 것 ③)
        log.warning("관련 노트 검색 실패, 링크 없이 진행합니다: %s", exc)
        result.related_lookup_failed = True

    date_str = markdown.current_date_str()
    filename = markdown.build_filename(result.title, date_str)
    # category 가 폴더다. 빼면 루트에 저장되고 재색인에 영영 안 잡힌다 (정한 것 ⑥)
    note_path = f"{result.category}/{filename}.md"

    note_body = markdown.build_note(
        title=result.title,
        summary=result.summary,
        tags=result.tags,
        category=result.category,
        date_str=date_str,
        original=message,
        related=result.related,
    )

    # 아래 두 저장은 독립적이다. 하나가 죽어도 나머지는 시도한다 (정한 것 ④)
    try:
        await github.save(
            path=note_path, content=note_body, message=f"Add: {result.title}"
        )
        result.github = SaveOutcome(ok=True)
    except Exception as exc:
        result.github = SaveOutcome(ok=False, error=errors.user_message(exc, "GitHub"))

    try:
        # 원본이 아니라 요약을 임베딩한다 — small-to-big (정한 것 ⑤)
        await pinecone.upsert_note(
            title=result.title, path=note_path, summary=result.summary
        )
        result.vector = SaveOutcome(ok=True)
    except Exception as exc:
        result.vector = SaveOutcome(ok=False, error=errors.user_message(exc, "Pinecone"))

    return result
