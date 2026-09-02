"""채팅 요청/응답 데이터 모양.

TS 대응: `const { message } = await req.json()` 는 타입이 any 였다.
Pydantic 모델을 쓰면 FastAPI가 요청 본문을 자동 검증하고,
형식이 틀리면 핸들러에 들어오기 전에 422 를 돌려준다.

프론트 계약을 깨지 않는 게 중요 —
ChatWindow.tsx 는 `{ reply: string }` 만 읽으므로 응답 키 이름을 바꾸면 안 된다.
"""

from typing import Literal

from pydantic import BaseModel, Field

# 저장 모드 / 질문 모드. TS: "save" | "question" 유니온과 동일 개념
Intent = Literal["save", "question"]


class ChatRequest(BaseModel):
    """POST /api/chat 요청 본문."""

    message: str = Field(min_length=1, description="사용자가 보낸 원문")


class ChatResponse(BaseModel):
    """POST /api/chat 응답. 프론트는 reply 한 필드만 렌더한다."""

    reply: str


class NoteHit(BaseModel):
    """벡터 검색 결과 한 건.

    핵심: 여기에 본문(content)이 없다. path 는 원본으로 가는 '포인터'일 뿐이고,
    실제 본문은 답변 단계에서 GitHub raw 로 따로 로드한다 (small-to-big).
    TS 대응: pinecone.ts:82-102 queryNotes 반환 타입
    """

    title: str
    path: str
    score: float


class LoadedNote(BaseModel):
    """원본 .md 를 실제로 읽어온 상태. 답변 생성 프롬프트에 들어간다."""

    name: str
    content: str


class SummaryResult(BaseModel):
    """Gemini 요약 결과.

    TS는 `JSON.parse()` 결과를 그대로 믿었다 (필드 누락/타입 오류 시 런타임에 터짐).
    Pydantic으로 받으면 파싱과 동시에 검증돼서, 여기를 통과하면 형식이 보장된다.
    TS 대응: gemini.ts:27-32 summarizeContent 반환 타입
    """

    title: str
    summary: str
    tags: list[str] = []
    category: Literal["articles", "concepts", "projects"]


class CollectRequest(BaseModel):
    """POST /api/collect 요청 본문.

    ★ chat 과 키 이름이 다르다 (message 가 아니라 content).
      iOS 단축어 같은 외부 도구가 이미 이 형식으로 보내고 있어서 바꾸면 깨진다.
    """

    content: str = Field(min_length=1, description="저장할 원문")


class CollectResponse(BaseModel):
    """POST /api/collect 응답. chat 과 달리 사람이 읽는 문장이 아니라 구조화된 JSON."""

    success: bool
    title: str
    summary: str
    tags: list[str]
    category: str
    saved: bool  # GitHub 저장 여부. TS 와 키 이름을 맞춘다
    indexed: bool  # 벡터DB 저장 여부. TS 에는 없던 필드(원본이 upsert 를 안 했다)


class SyncResponse(BaseModel):
    """POST /api/sync 응답. 키 이름은 TS(sync/route.ts:51-57)와 동일하게 유지."""

    message: str
    synced: int
    failed: int
    skipped: int
    total: int
