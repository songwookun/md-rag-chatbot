import { NextRequest } from "next/server";
import { proxy } from "@/lib/proxy";

// 저장 / 질문 — 분기와 판단은 전부 백엔드(services/)에 있다.
// errorKey: ChatWindow 가 data.reply 를 말풍선에 렌더하므로 실패 문구도 같은 키로.
export async function POST(req: NextRequest) {
  return proxy(req, "/api/chat", { errorKey: "reply" });
}
