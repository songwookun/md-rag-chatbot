function getGitHubConfig() {
  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPO;
  if (!token || !repo) throw new Error("GitHub not configured");
  return { token, repo };
}

export async function saveToGitHub({
  path,
  content,
  message,
}: {
  path: string;
  content: string;
  message: string;
}) {
  const { token, repo } = getGitHubConfig();

  const res = await fetch(
    `https://api.github.com/repos/${repo}/contents/${path}`,
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
        content: Buffer.from(content).toString("base64"),
      }),
    }
  );

  if (!res.ok) {
    const err = await res.json();
    throw new Error(`GitHub API error: ${err.message}`);
  }

  return res.json();
}

// GitHub repo에서 기존 노트 목록 가져오기
export async function getExistingNotes(): Promise<
  { name: string; path: string }[]
> {
  const { token, repo } = getGitHubConfig();
  const folders = ["articles", "concepts", "projects"];
  const notes: { name: string; path: string }[] = [];

  for (const folder of folders) {
    try {
      const res = await fetch(
        `https://api.github.com/repos/${repo}/contents/${folder}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) continue;
      const files = await res.json();
      for (const file of files) {
        if (file.name.endsWith(".md")) {
          notes.push({
            name: file.name.replace(/\.md$/, "").replace(/^\d{4}-\d{2}-\d{2}-/, ""),
            path: file.path,
          });
        }
      }
    } catch {
      continue;
    }
  }

  return notes;
}

// RAG용: 모든 노트의 전체 내용 가져오기
export async function getAllNoteContents(): Promise<
  { name: string; path: string; content: string }[]
> {
  const { token, repo } = getGitHubConfig();
  const notes = await getExistingNotes();

  // 최대 30개 노트까지 병렬로 내용 가져오기
  const notesToFetch = notes.slice(0, 30);
  const results = await Promise.all(
    notesToFetch.map(async (note) => {
      try {
        const res = await fetch(
          `https://api.github.com/repos/${repo}/contents/${note.path}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              Accept: "application/vnd.github.raw",
            },
          }
        );
        if (!res.ok) return null;
        const content = await res.text();
        return { name: note.name, path: note.path, content };
      } catch {
        return null;
      }
    })
  );

  return results.filter(
    (r): r is { name: string; path: string; content: string } => r !== null
  );
}

// RAG 답변용: 단일 경로의 원본 .md를 raw로 로드 (★ small-to-big: 원본으로 답)
export async function getNoteContent(path: string): Promise<string> {
  const { token, repo } = getGitHubConfig();
  const res = await fetch(
    `https://api.github.com/repos/${repo}/contents/${path}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.raw", // base64 말고 원문 그대로
      },
    }
  );
  if (!res.ok) throw new Error(`GitHub raw load 실패: ${path}`);
  return res.text();
}

// 재색인용: 원본 markdown에서 "## 요약" 섹션만 추출 (다음 ## 전까지)
export function extractSummary(markdown: string): string {
  const m = markdown.match(/##\s*요약\s*\n([\s\S]*?)(?=\n##\s|$)/);
  return m ? m[1].trim() : "";
}
