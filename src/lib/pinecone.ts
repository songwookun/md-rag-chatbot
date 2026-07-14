import { Pinecone } from "@pinecone-database/pinecone";
import { getEmbedding } from "./gemini";

let pineconeClient: Pinecone | null = null;

function getPinecone() {
  if (!pineconeClient) {
    pineconeClient = new Pinecone({
      apiKey: process.env.PINECONE_API_KEY!,
    });
  }
  return pineconeClient;
}

function getIndex() {
  return getPinecone().index(process.env.PINECONE_INDEX!);
}

// 한글 경로를 ASCII ID로 변환
function toAsciiId(path: string): string {
  return Buffer.from(path).toString("base64url");
}

// 관련 노트 찾기 = LLM 추측 대신 벡터 유사도 (저장 전 호출 → 새 노트는 아직 인덱스에 없어 self-match 없음)
const RELATED_THRESHOLD = 0.6;
export async function findRelatedNotes(
  text: string,
  topK: number = 3
): Promise<string[]> {
  const index = getIndex();
  const embedding = await getEmbedding(text, { isQuery: true });
  const results = await index.query({
    vector: embedding,
    topK,
    includeMetadata: true,
  });
  return (results.matches || [])
    .filter((m) => (m.score ?? 0) >= RELATED_THRESHOLD)
    .map((m) => (m.metadata?.title as string) || "")
    .filter(Boolean);
}

// 재색인 전 인덱스 전체 비우기 (옛 방식 벡터가 혼합되지 않도록)
export async function clearIndex() {
  try {
    await getIndex().deleteAll();
  } catch (e) {
    // 비어있는 인덱스면 "namespace not found"가 날 수 있음 → 무시
    const msg = e instanceof Error ? e.message : String(e);
    if (!/not found|404/i.test(msg)) throw e;
  }
}

// 노트를 벡터로 변환하여 Pinecone에 저장 (★ 요약을 임베딩 = small-to-big의 저장 쪽)
export async function upsertNote(note: {
  title: string;
  path: string;
  summary: string;
}) {
  const index = getIndex();
  const embedding = await getEmbedding(note.summary, { isQuery: false }); // 요약을 문서로 임베딩

  await index.upsert({
    records: [
      {
        id: toAsciiId(note.path),
        values: embedding,
        metadata: {
          title: note.title,
          path: note.path, // ★ 원본으로 가는 포인터
          summary: note.summary, // 싸게 갈 때 fallback용(선택)
        },
      },
    ],
  });
}

// ★ 실측 튜닝값(2026-07-14): 관련 0.64+, 무관 0.58- 사이의 골. Gemini는 무관도 점수 높게 눌려나와 0.5는 낮음
const THRESHOLD = 0.6;

// 질문과 의미가 가까운 노트를 검색 = "찾기"만 (원본 로드는 답변 단계가 path로)
export async function queryNotes(
  question: string,
  topK: number = 5
): Promise<{ title: string; path: string; score: number }[]> {
  const index = getIndex();
  const embedding = await getEmbedding(question, { isQuery: true }); // ★ 질문 임베딩

  const results = await index.query({
    vector: embedding,
    topK,
    includeMetadata: true,
  });

  return (results.matches || [])
    .filter((m) => (m.score ?? 0) >= THRESHOLD) // ★ abstention
    .map((m) => ({
      title: (m.metadata?.title as string) || "",
      path: (m.metadata?.path as string) || "", // ★ 원본 포인터만 반환
      score: m.score ?? 0,
    }));
}

