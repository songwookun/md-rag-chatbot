import { GoogleGenerativeAI, TaskType } from "@google/generative-ai";

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);

const geminiModel = genAI.getGenerativeModel({
  model: "gemini-2.5-flash",
});

// 텍스트를 벡터(임베딩)로 변환. 문서/질문 공용 — taskType만 분기 (원칙 #1)
export async function getEmbedding(
  text: string,
  opts: { isQuery?: boolean } = {} // 기본 false = 문서(저장)
): Promise<number[]> {
  const embeddingModel = genAI.getGenerativeModel({
    model: "gemini-embedding-001",
  });
  const result = await embeddingModel.embedContent({
    content: { role: "user", parts: [{ text }] }, // taskType 같이 넘기려면 객체 형태
    taskType: opts.isQuery
      ? TaskType.RETRIEVAL_QUERY // 질문
      : TaskType.RETRIEVAL_DOCUMENT, // 저장(문서)
  });
  return result.embedding.values;
}

// LLM은 요약·명명·분류만 (관련노트=벡터검색, type=URL판별로 코드가 처리)
export async function summarizeContent(input: string): Promise<{
  title: string;
  summary: string;
  tags: string[];
  category: string;
}> {
  const prompt = `당신은 지식 정리 어시스턴트입니다.

사용자가 보낸 내용을 분석해서 아래 JSON 형식으로 정리해주세요.

입력: ${input}

반드시 아래 JSON 형식으로만 응답하세요 (마크다운 코드블록 없이):
{
  "title": "제목 (간결하게)",
  "summary": "핵심 내용 요약 (3-5문장)",
  "tags": ["태그1", "태그2", "태그3"],
  "category": "articles | concepts | projects 중 하나"
}`;

  const result = await geminiModel.generateContent(prompt);
  const text = result.response.text().trim();

  // JSON 파싱 (코드블록 감싸져 있을 경우 처리)
  const jsonStr = text.replace(/```json?\n?/g, "").replace(/```/g, "").trim();
  return JSON.parse(jsonStr);
}

// 사용자 입력이 저장할 콘텐츠인지 질문인지 판별
export async function classifyIntent(
  message: string
): Promise<"save" | "question"> {
  const text = message.trim();

  // ① URL 포함 → 저장 (코드가 확실히 앎)
  if (/https?:\/\/[^\s]+/.test(text)) return "save";

  // ② 긴 텍스트 → 저장 (질문을 이렇게 길게 안 씀. "검색" 같은 단어 있어도 저장)
  if (text.length >= 150) return "save";

  // ③ 짧은 텍스트 + 의문 표현 → 질문
  const questionPatterns =
    /[?？]|뭐|뭔|어때|어떻|어떡|왜|무엇|설명|알려|찾아|검색|어디|언제|누가|몇|얼마|인가|인지|할까|일까|줘$|줄래|있어|있나/;
  if (questionPatterns.test(text)) return "question";

  // ④ 짧고 의문 표현도 없음 = 진짜 애매 → 여기서만 LLM (드묾)
  const prompt = `사용자 메시지를 분류하세요.
- "save": 저장할 정보, 링크, 메모, 학습 내용
- "question": 질문, 검색, 이전에 저장한 내용에 대한 문의

"save" 또는 "question" 중 하나만 응답하세요.

메시지: "${message}"`;

  const result = await geminiModel.generateContent(prompt);
  const answer = result.response.text().trim().toLowerCase();
  return answer.includes("question") ? "question" : "save";
}

// RAG: 저장된 노트를 기반으로 질문에 답변
export async function answerFromNotes(
  question: string,
  notes: { name: string; content: string }[]
): Promise<string> {
  const notesContext = notes
    .map((n) => `--- [${n.name}] ---\n${n.content}`)
    .join("\n\n");

  const prompt = `당신은 사용자의 개인 지식 베이스(아래 [자료])만 근거로 답하는 어시스턴트입니다.

[자료] — 사용자가 저장한 노트 원본:
${notesContext}

---
사용자 질문: ${question}

[엄수 규칙]
- 오직 위 [자료]에 실제로 적힌 내용만 근거로 답하세요. 당신이 학습으로 아는 외부 지식·사전 상식은 절대 사용하지 마세요.
- [자료]에 없는 내용은 추측하거나 보완하지 말고, 없다고 명시하세요: "저장된 노트에 해당 내용이 없습니다."
- 근거로 사용한 노트는 [[노트이름]] 형식으로 표시하세요.
- 여러 노트를 종합해도 되지만, [자료] 밖의 사실은 한 문장도 추가하지 마세요.
- 한국어로 답하세요.`;

  const result = await geminiModel.generateContent(prompt);
  return result.response.text();
}
