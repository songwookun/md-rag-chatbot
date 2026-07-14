import { NextRequest, NextResponse } from "next/server";
import { summarizeContent } from "@/lib/gemini";
import { saveToGitHub } from "@/lib/github";
import { findRelatedNotes } from "@/lib/pinecone";

const URL_REGEX = /https?:\/\/[^\s]+/;

export async function POST(req: NextRequest) {
  // 인증 확인
  const authHeader = req.headers.get("authorization");
  if (authHeader !== `Bearer ${process.env.AUTH_PASSWORD}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const { content } = await req.json();

    if (!content || typeof content !== "string") {
      return NextResponse.json(
        { error: "content is required" },
        { status: 400 }
      );
    }

    const isLink = URL_REGEX.test(content);

    // Gemini는 요약/제목/태그/분류만
    const result = await summarizeContent(content);

    // 관련 노트 = 벡터 유사도 (LLM 추측 대신)
    let relatedNotes: string[] = [];
    try {
      relatedNotes = await findRelatedNotes(result.summary);
    } catch {
      // 실패해도 저장은 진행
    }

    // 마크다운 생성
    const now = new Date();
    const dateStr = now.toISOString().split("T")[0];
    const fileName = `${dateStr}-${result.title
      .replace(/[^a-zA-Z0-9가-힣\s]/g, "")
      .replace(/\s+/g, "-")
      .slice(0, 50)}`;

    const markdown = `---
title: "${result.title}"
date: ${dateStr}
tags: [${result.tags.map((t) => `"${t}"`).join(", ")}]
category: ${result.category}
type: ${isLink ? "link" : "text"}
source: "${isLink ? content.match(URL_REGEX)?.[0] : ""}"
---

# ${result.title}

## 요약
${result.summary}

## 원본
${content}

## 태그
${result.tags.map((t) => `#${t}`).join(" ")}
${relatedNotes.length > 0 ? `\n## 관련 노트\n${relatedNotes.map((n) => `- [[${n}]]`).join("\n")}\n` : ""}`;

    // GitHub 저장
    let saved = false;
    try {
      await saveToGitHub({
        path: `${result.category}/${fileName}.md`,
        content: markdown,
        message: `Add: ${result.title}`,
      });
      saved = true;
    } catch {
      // GitHub 미설정 시 무시
    }

    return NextResponse.json({
      success: true,
      title: result.title,
      summary: result.summary,
      tags: result.tags,
      category: result.category,
      saved,
    });
  } catch (error) {
    console.error("Collect API error:", error);
    return NextResponse.json(
      { error: "Processing failed" },
      { status: 500 }
    );
  }
}
