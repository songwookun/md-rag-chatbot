"""외부 수집 엔드포인트 — 브라우저 밖에서 노트를 밀어넣는 통로.

TS 원본: src/app/api/collect/route.ts
용도: iOS 단축어 등이 호출한다.


chat 과의 차이
────────────────────────────────────────────────────────────────
    인증  쿠키가 아니라 Authorization: Bearer <AUTH_PASSWORD> 헤더
          브라우저가 아니라 외부 도구가 부르므로 쿠키가 없다
    입력  {"content": "..."}   (chat 은 {"message": "..."})
    출력  구조화된 JSON        (chat 은 사람이 읽을 문자열)
    분기  없다 — 무조건 저장 (질문 모드가 없다)


★ 여기서 리팩터링의 이득이 드러난다 — 원본의 버그가 사라졌다
────────────────────────────────────────────────────────────────
TS 원본은 chat 의 저장 로직(요약 → 관련노트 → 마크다운 → 저장)을 이 파일에
통째로 복사해뒀다. 그런데 복사하면서 **Pinecone upsert 를 빠뜨렸다**
(collect/route.ts:67-78 은 GitHub 저장만 한다).

결과: iOS 단축어로 넣은 노트는 GitHub 에는 있는데 **검색이 안 됐다.**
재색인을 돌려야 비로소 잡혔고, 그 사이에는 "저장했는데 왜 못 찾지?"가 된다.

services/ingest.py 로 뽑아서 두 엔드포인트가 같은 함수를 부르게 하니
이 버그는 고칠 필요도 없이 없어졌다. **복사된 코드는 언젠가 갈라진다.**


정한 것
────────────────────────────────────────────────────────────────
① 응답에 indexed 를 추가했다
   TS 는 saved(GitHub 저장 여부)만 돌려줬다. 이제 벡터 저장도 하므로 결과가 둘이다.
   saved 는 키 이름을 그대로 뒀다 — 외부 도구가 이미 읽고 있을 수 있다.

② 저장 실패해도 200 이다
   success 는 "요청을 처리했다"는 뜻이고, 무엇이 저장됐는지는 saved/indexed 가 말한다.
   외부 도구가 상태 코드만 보고 재시도하면 노트가 두 개 생긴다.
"""

from fastapi import APIRouter, Depends

from app.api.deps import require_bearer
from app.schemas.chat import CollectRequest, CollectResponse
from app.services import ingest as ingest_service

router = APIRouter()


@router.post("/collect", response_model=CollectResponse)
async def collect(
    body: CollectRequest, _: None = Depends(require_bearer)
) -> CollectResponse:
    """외부에서 보낸 콘텐츠를 노트로 저장한다. chat 과 같은 파이프라인을 쓴다."""
    result = await ingest_service.ingest(body.content)

    return CollectResponse(
        success=True,
        title=result.title,
        summary=result.summary,
        tags=result.tags,
        category=result.category,
        saved=result.github.ok,
        indexed=result.vector.ok,  # TS 에는 없던 값 — 원본이 upsert 를 안 했다
    )
