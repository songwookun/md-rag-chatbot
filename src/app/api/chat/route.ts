import { NextRequest, NextResponse } from "next/server";
import { summarizeContent, classifyIntent, answerFromNotes } from "@/lib/gemini";
import { saveToGitHub, getNoteContent } from "@/lib/github";
import { queryNotes, upsertNote, findRelatedNotes } from "@/lib/pinecone";
import { verifyAuthToken, unauthorizedResponse } from "@/lib/auth";

// URL 패턴 감지
const URL_REGEX = /https?:\/\/[^\s]+/;

// 에러 메시지 분류
function getErrorMessage(e: unknown, service: string): string {
  const msg = e instanceof Error ? e.message : String(e);

  // Gemini API 에러
  if (service === "Gemini") {
    if (msg.includes("429") || msg.includes("quota") || msg.includes("RESOURCE_EXHAUSTED"))
      return "⚠️ Gemini API 사용량이 소진되었습니다. Google AI Studio에서 할당량을 확인해주세요.";
    if (msg.includes("401") || msg.includes("403") || msg.includes("API_KEY_INVALID"))
      return "⚠️ Gemini API 키가 유효하지 않습니다. 키를 재발급해주세요.";
    if (msg.includes("404"))
      return "⚠️ Gemini 모델을 찾을 수 없습니다. 모델명을 확인해주세요.";
  }

  // GitHub 에러
  if (service === "GitHub") {
    if (msg.includes("401") || msg.includes("Bad credentials"))
      return "⚠️ GitHub 토큰이 만료되었습니다. 새 토큰을 발급해주세요.";
    if (msg.includes("403") || msg.includes("rate limit"))
      return "⚠️ GitHub API 호출 한도를 초과했습니다. 잠시 후 다시 시도해주세요.";
    if (msg.includes("404"))
      return "⚠️ GitHub 저장소를 찾을 수 없습니다. GITHUB_REPO 설정을 확인해주세요.";
    if (msg.includes("422"))
      return "⚠️ GitHub 저장 실패: 같은 이름의 파일이 이미 존재합니다.";
  }

  // Pinecone 에러
  if (service === "Pinecone") {
    if (msg.includes("401") || msg.includes("Unauthorized") || msg.includes("UNAUTHENTICATED"))
      return "⚠️ Pinecone API 키가 유효하지 않습니다. 키를 확인해주세요.";
    if (msg.includes("404") || msg.includes("not found"))
      return "⚠️ Pinecone 인덱스를 찾을 수 없습니다. PINECONE_INDEX 설정을 확인해주세요.";
    if (msg.includes("dimension"))
      return "⚠️ Pinecone 벡터 차원이 일치하지 않습니다. 인덱스를 3072 차원으로 재생성해주세요.";
    if (msg.includes("quota") || msg.includes("limit"))
      return "⚠️ Pinecone 무료 한도를 초과했습니다. 사용량을 확인해주세요.";
  }

  return `⚠️ ${service} 오류: ${msg}`;
}

export async function POST(req: NextRequest) {
  // 인증 확인
  if (!verifyAuthToken(req)) {
    return unauthorizedResponse();
  }

  try {
    const { message } = await req.json();

    // 의도 분류: 저장 vs 질문
    let intent: "save" | "question";
    try {
      intent = await classifyIntent(message);
    } catch (e) {
      console.error("Gemini classify error:", e);
      return NextResponse.json({
        reply: getErrorMessage(e, "Gemini"),
      });
    }

    // === 질문 모드 (RAG: 찾기=벡터, 답하기=원본) ===
    if (intent === "question") {
      // 1) 찾기 — 벡터 유사도 + 임계값(abstention). path만 돌려받음
      let hits: { title: string; path: string; score: number }[] = [];
      try {
        hits = await queryNotes(message, 5);
      } catch (e) {
        console.error("Pinecone query error:", e);
        return NextResponse.json({
          reply: getErrorMessage(e, "Pinecone"),
        });
      }

      // 임계값에 다 걸러지면 지어내지 않고 abstain
      if (hits.length === 0) {
        return NextResponse.json({
          reply:
            "저장된 노트 중 이 질문과 관련된 내용을 찾지 못했습니다. (지어내지 않고 답변을 보류합니다)",
        });
      }

      // 2) ★ small-to-big — path로 GitHub 원본 .md 로드 (로드 실패한 건 스킵)
      let notes: { name: string; content: string }[] = [];
      try {
        const loaded = await Promise.all(
          hits.map(async (h) => {
            try {
              return { name: h.title, content: await getNoteContent(h.path) };
            } catch {
              return null; // 개별 노트 로드 실패는 무시하고 나머지로 답변
            }
          })
        );
        notes = loaded.filter(
          (n): n is { name: string; content: string } => n !== null
        );
      } catch (e) {
        console.error("GitHub load error:", e);
        return NextResponse.json({ reply: getErrorMessage(e, "GitHub") });
      }

      // 원본을 하나도 못 불러왔으면 역시 abstain
      if (notes.length === 0) {
        return NextResponse.json({
          reply: "관련 노트를 찾았지만 원본을 불러오지 못했습니다.",
        });
      }

      // 3) 답하기 — 원본을 근거로 생성 (grounding)
      try {
        const answer = await answerFromNotes(message, notes);
        return NextResponse.json({ reply: answer });
      } catch (e) {
        console.error("Gemini answer error:", e);
        return NextResponse.json({
          reply: getErrorMessage(e, "Gemini"),
        });
      }
    }

    // === 저장 모드 ===
    const isLink = URL_REGEX.test(message);

    // Gemini는 요약/제목/태그/분류만 (관련노트는 아래에서 벡터로)
    let result;
    try {
      result = await summarizeContent(message);
    } catch (e) {
      console.error("Gemini summarize error:", e);
      return NextResponse.json({
        reply: getErrorMessage(e, "Gemini"),
      });
    }

    // 관련 노트 = 벡터 유사도로 찾음 (LLM 추측 대신). 실패해도 저장은 진행
    let relatedNotes: string[] = [];
    try {
      relatedNotes = await findRelatedNotes(result.summary);
    } catch (e) {
      console.error("findRelatedNotes error:", e);
    }

    // Obsidian 마크다운 형식으로 변환
    const now = new Date();
    const dateStr = now.toISOString().split("T")[0];
    const fileName = `${dateStr}-${result.title
      .replace(/[^a-zA-Z0-9가-힣\s]/g, "")
      .replace(/\s+/g, "-")
      .slice(0, 50)}`;

    // [[링크]] 섹션 생성 (벡터로 찾은 관련 노트)
    const relatedLinks =
      relatedNotes.length > 0
        ? `\n## 관련 노트\n${relatedNotes.map((n) => `- [[${n}]]`).join("\n")}\n`
        : "";

    const markdown = `---
title: "${result.title}"
date: ${dateStr}
tags: [${result.tags.map((t) => `"${t}"`).join(", ")}]
category: ${result.category}
type: ${isLink ? "link" : "text"}
source: "${isLink ? message.match(URL_REGEX)?.[0] : ""}"
---

# ${result.title}

## 요약
${result.summary}

## 원본
${message}

## 태그
${result.tags.map((t) => `#${t}`).join(" ")}
${relatedLinks}`;

    // GitHub 저장 시도
    let saved = false;
    let githubError = "";
    const notePath = `${result.category}/${fileName}.md`;
    try {
      await saveToGitHub({
        path: notePath,
        content: markdown,
        message: `Add: ${result.title}`,
      });
      saved = true;
    } catch (e) {
      console.error("GitHub save error:", e);
      githubError = getErrorMessage(e, "GitHub");
    }

    // Pinecone에 벡터 저장
    let vectorSaved = false;
    let pineconeError = "";
    try {
      await upsertNote({
        title: result.title,
        path: notePath,
        summary: result.summary, // ★ 요약을 임베딩 (원본은 GitHub에)
      });
      vectorSaved = true;
    } catch (e) {
      console.error("Pinecone upsert error:", e);
      pineconeError = getErrorMessage(e, "Pinecone");
    }

    const relatedInfo =
      relatedNotes.length > 0
        ? `\n**관련 노트**: ${relatedNotes.map((n) => `[[${n}]]`).join(", ")}`
        : "";

    // 저장 상태 메시지
    let saveStatus = "";
    if (saved && vectorSaved) {
      saveStatus = "\n✅ 저장 완료 (GitHub + 벡터DB)";
    } else if (saved && !vectorSaved) {
      saveStatus = `\n✅ GitHub 저장 완료\n${pineconeError}`;
    } else if (!saved && vectorSaved) {
      saveStatus = `\n✅ 벡터DB 저장 완료\n${githubError}`;
    } else {
      saveStatus = `\n${githubError}\n${pineconeError}`;
    }

    const reply = `**${result.title}**

${result.summary}

**분류**: ${result.category}
**태그**: ${result.tags.map((t) => `#${t}`).join(" ")}${relatedInfo}
${saveStatus}`;

    return NextResponse.json({ reply });
  } catch (error) {
    console.error("Chat API error:", error);
    const msg = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { reply: `⚠️ 처리 중 오류가 발생했습니다: ${msg}` },
      { status: 500 }
    );
  }
}
