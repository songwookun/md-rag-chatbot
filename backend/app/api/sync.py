"""재색인 엔드포인트 — GitHub 노트 전체를 벡터DB에 다시 색인한다.

TS 원본: src/app/api/sync/route.ts

용도: 두 저장소가 어긋났을 때(저장 중 한쪽만 성공했을 때) 복구하는 수단.
GitHub 이 원본(source of truth)이고 벡터DB는 파생 데이터라는 관계가 여기서 드러난다.
그래서 복구 방향이 GitHub → 벡터DB 한쪽뿐이다.


★ 이 파일에서 제일 중요한 줄 — 0개면 아무것도 하지 않는다
────────────────────────────────────────────────────────────────
노트를 0개 읽어왔을 때, 그게 "진짜 노트가 없는 것"인지 "GitHub 읽기가 실패한 것"인지
구분할 방법이 없다. 구분이 안 되는데 clear_index() 를 부르면 **멀쩡한 벡터DB를 통째로
날린다.** GitHub 이 잠깐 죽은 날 재색인 버튼을 누르면 검색이 전부 사라진다는 뜻이다.

**읽기 실패와 진짜 빈 상태를 구분할 수 없으면 파괴적 작업을 하지 않는다.**
(TS: sync/route.ts:16-25 — 이 판단은 원본이 맞게 했다)


정한 것
────────────────────────────────────────────────────────────────
① Gemini 를 다시 부르지 않는다
   요약은 이미 .md 안의 "## 요약" 섹션에 적혀 있다. 읽어서 쓰면 API 비용이 0이다.
   저장 때와 같은 텍스트를 임베딩해야 벡터가 일관된다는 이유도 있다.

② "## 요약" 이 없는 노트는 실패가 아니라 스킵이다
   옛 형식으로 저장된 노트다. 실패로 세면 사용자가 고칠 수 없는 숫자가 남는다.
   skipped 를 따로 세서 "요약 없음"임을 알린다.

③ 지우고 다시 넣는다 (증분 갱신이 아니라)
   옛 방식으로 만들어진 벡터가 새 벡터와 섞이면 점수 분포가 망가진다.
   차원이나 임베딩 설정을 바꿨을 때 특히 그렇다.

④ 노트 하나의 실패가 전체를 멈추지 않는다
   50개 중 3개가 실패해도 47개는 색인돼야 한다. 실패 수만 세서 알린다.


여유되면
────────────────────────────────────────────────────────────────
노트가 많아지면 순차 루프가 느리다. asyncio.gather 로 묶되 Pinecone 레이트리밋에
걸리지 않게 세마포어로 동시 실행 수를 제한할 것. 지금은 20개라 순차로 충분하다.
"""

import logging

from fastapi import APIRouter, Depends

from app.adapters import github, pinecone
from app.api.deps import require_auth
from app.core import markdown
from app.schemas.chat import SyncResponse

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/sync", response_model=SyncResponse)
async def sync(_: None = Depends(require_auth)) -> SyncResponse:
    """GitHub 노트를 전부 다시 색인한다. 읽어온 게 0개면 아무것도 지우지 않는다."""
    notes = await github.get_all_contents()

    # ★ 0개일 때 clear_index 를 부르면 멀쩡한 인덱스를 날린다 (파일 상단 참고)
    if not notes:
        return SyncResponse(
            message="동기화할 노트가 없습니다 (GitHub에서 노트를 찾지 못함).",
            synced=0,
            failed=0,
            skipped=0,
            total=0,
        )

    await pinecone.clear_index()

    synced = failed = skipped = 0
    for note in notes:
        # 원본에서 요약만 뽑아 재임베딩 — Gemini 재호출 없음 (정한 것 ①)
        summary = markdown.extract_summary(note["content"])
        if not summary:
            # "## 요약" 이 없는 옛 형식 노트 — 실패가 아니다 (정한 것 ②)
            skipped += 1
            continue
        try:
            await pinecone.upsert_note(
                title=note["name"], path=note["path"], summary=summary
            )
            synced += 1
        except Exception as exc:
            # 하나가 실패해도 나머지는 계속한다 (정한 것 ④)
            log.warning("재색인 실패: %s (%s)", note["path"], exc)
            failed += 1

    return SyncResponse(
        message=(
            f"재색인 완료: {synced}개 성공, {failed}개 실패, "
            f"{skipped}개 스킵(요약 없음) (전체 {len(notes)}개)"
        ),
        synced=synced,
        failed=failed,
        skipped=skipped,
        total=len(notes),
    )
