"""저장 파이프라인 — 사용자 입력을 노트로 만들어 GitHub + Pinecone 에 넣는다.

TS 원본: src/app/api/chat/route.ts:131-244

=== 4단계. 이 파일은 직접 구현할 핵심 로직 ===

흐름:
    입력
     → gemini.summarize            제목/요약/태그/분류
     → pinecone.find_related       관련 노트 (★ upsert 전에! self-match 방지)
     → markdown.build_note         .md 본문 조립
     → github.save                 ┐ 서로 독립. 하나 실패해도
     → pinecone.upsert_note        ┘ 다른 하나는 진행
     → 결과 메시지

★ 이 파이프라인의 설계 원칙 — '부분 실패 허용'
  GitHub 저장과 벡터 저장은 별개 시스템이다. 하나가 죽었다고 나머지를 버리면
  사용자는 아무것도 못 건진다. 각각 try 로 감싸고, 무엇이 됐고 무엇이 안 됐는지
  사용자에게 정확히 알려주는 게 낫다. (TS: chat/route.ts:226-234 의 4가지 분기)
  단, 이러면 두 저장소가 어긋난 상태가 생길 수 있고 → 그걸 고치는 게 sync(재색인)다.
"""

from dataclasses import dataclass, field


@dataclass
class IngestResult:
    """저장 시도 결과. api/chat.py 가 이걸 사용자 메시지로 바꾼다.

    ★ 서비스는 '무슨 일이 있었는지'만 반환하고, 문장 만들기는 api 층에 맡긴다.
      이렇게 나눠야 서비스 로직을 UI 문구와 무관하게 테스트할 수 있다.
    """

    title: str = ""
    summary: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    saved_to_github: bool = False
    saved_to_vector: bool = False
    github_error: str = ""
    vector_error: str = ""


async def ingest(message: str) -> IngestResult:
    """저장 파이프라인 실행.

    TODO(4단계): 구현

      [1] 요약
          result = await gemini.summarize(message)
          ※ 여기서 실패하면 더 진행할 수 없다 → 예외를 그대로 올려보내
            api/chat.py 가 Gemini 에러 메시지로 변환하게 한다.

      [2] 관련 노트 (실패해도 저장은 계속)
          try: related = await pinecone.find_related(result.summary)
          except: related = []            ← ★ 부가 기능이라 실패를 삼킨다
          ★ 반드시 upsert 전에 호출. 순서 바꾸면 새 노트가 자기 자신을 관련 노트로 집는다.

      [3] 경로 결정
          date_str = datetime.now().strftime("%Y-%m-%d")
          filename = markdown.build_filename(result.title, date_str)
          note_path = f"{result.category}/{filename}.md"
          ※ category 가 곧 폴더명이다 (articles/concepts/projects)

      [4] 본문 조립
          source_url 은 message 에서 URL 정규식으로 추출 (없으면 "")
          body = markdown.build_note(result=..., original=message, ...)

      [5] 두 저장소에 각각 독립적으로 저장
          try: await github.save(path=note_path, content=body,
                                 message=f"Add: {result.title}")
               saved_to_github = True
          except as e: github_error = errors.user_message(e, "GitHub")

          try: await pinecone.upsert_note(title=..., path=note_path,
                                          summary=result.summary)
               saved_to_vector = True
          except as e: vector_error = errors.user_message(e, "Pinecone")

          ★ upsert 에 넘기는 summary 는 원본이 아니라 요약이다 (small-to-big)

      [6] IngestResult 로 묶어서 반환

      === 여유되면 생각해볼 것 ===
      [5]의 두 저장을 asyncio.gather 로 동시에 돌리면 더 빠르다.
      다만 return_exceptions=True 로 받아야 하나가 죽어도 나머지가 산다.
      먼저 순차로 동작시킨 뒤 바꿔볼 것 — 동작하는 코드부터 만들고 최적화는 그다음.
    """
    raise NotImplementedError
