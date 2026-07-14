import { NextRequest, NextResponse } from "next/server";
import { getAllNoteContents, extractSummary } from "@/lib/github";
import { upsertNote, clearIndex } from "@/lib/pinecone";
import { verifyAuthToken, unauthorizedResponse } from "@/lib/auth";

// 기존 GitHub 노트를 Pinecone에 일괄 동기화
export async function POST(req: NextRequest) {
  // 인증 확인
  if (!verifyAuthToken(req)) {
    return unauthorizedResponse();
  }

  try {
    const notes = await getAllNoteContents();

    // GitHub 읽기가 0개면 인덱스를 날리지 않음 (읽기 실패 시 데이터 유실 방지)
    if (notes.length === 0) {
      return NextResponse.json({
        message: "동기화할 노트가 없습니다 (GitHub에서 노트를 찾지 못함).",
        synced: 0,
        failed: 0,
        skipped: 0,
        total: 0,
      });
    }

    // 옛 방식 벡터가 섞이지 않도록 전체 비우고 처음부터 재색인
    await clearIndex();

    let synced = 0;
    let failed = 0;
    let skipped = 0;

    for (const note of notes) {
      // 원본 markdown에서 요약만 뽑아 재임베딩 (Gemini 재호출 X)
      const summary = extractSummary(note.content);
      if (!summary) {
        // ## 요약 섹션이 없는 옛 형식 노트는 스킵
        skipped++;
        continue;
      }
      try {
        await upsertNote({ title: note.name, path: note.path, summary });
        synced++;
      } catch (e) {
        console.error(`Failed to sync ${note.name}:`, e);
        failed++;
      }
    }

    return NextResponse.json({
      message: `재색인 완료: ${synced}개 성공, ${failed}개 실패, ${skipped}개 스킵(요약 없음) (전체 ${notes.length}개)`,
      synced,
      failed,
      skipped,
      total: notes.length,
    });
  } catch (error) {
    console.error("Sync error:", error);
    return NextResponse.json(
      { message: "동기화 중 오류가 발생했습니다." },
      { status: 500 }
    );
  }
}
