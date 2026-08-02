"""재색인 엔드포인트 — GitHub 노트 전체를 Pinecone 에 다시 색인.

TS 원본: src/app/api/sync/route.ts

용도: GitHub 와 벡터DB가 어긋났을 때(저장 중 한쪽만 성공했을 때) 복구하는 수단.
GitHub 가 원본(source of truth), 벡터DB는 파생 데이터라는 관계가 여기서 드러난다.

=== 7단계에서 구현 ===
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/sync")
async def sync():
    """전체 재색인.

    TS 대응: sync/route.ts:7-65

    TODO(7단계): 구현

      [1] notes = await github.get_all_contents()

      [2] ★ 안전장치 — notes 가 0개면 여기서 즉시 반환한다.
          이유: GitHub 읽기가 실패했을 때도 0개가 나온다.
          그 상태로 clear_index() 를 부르면 멀쩡한 벡터DB를 통째로 날린다.
          "읽기 실패와 진짜 빈 상태를 구분할 수 없으면 파괴적 작업을 하지 않는다."
          (TS: sync/route.ts:16-25 — 이 판단은 꼭 옮길 것)

      [3] await pinecone.clear_index()
          옛 방식으로 만들어진 벡터가 섞이면 점수 분포가 망가지므로 지우고 시작

      [4] 노트별 루프
          summary = markdown.extract_summary(note["content"])
          if not summary: skipped += 1; continue
            ← "## 요약" 섹션이 없는 옛 형식 노트
          try: await pinecone.upsert_note(...); synced += 1
          except: failed += 1
          ★ Gemini 를 다시 부르지 않는다 — 요약은 이미 .md 안에 있다. API 비용 0.

      [5] {"message": ..., "synced":, "failed":, "skipped":, "total":} 반환
          ※ 응답 키 이름은 TS 와 맞출 것 (프론트에서 쓰고 있다면 깨진다)

      === 여유되면 ===
      노트가 많아지면 순차 루프가 느리다. asyncio.gather 로 묶되
      Pinecone 레이트리밋에 걸리지 않게 세마포어로 동시 실행 수를 제한할 것.
    """
    raise NotImplementedError
