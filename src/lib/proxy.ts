import { NextRequest } from "next/server";

/**
 * Next API 라우트 → FastAPI 백엔드로 요청을 그대로 넘기는 얇은 프록시.
 *
 * 왜 프록시인가 (rewrite 나 프론트에서 직접 호출 대신)
 * ────────────────────────────────────────────────────────────
 * ① 컴포넌트 수정 0줄 — ChatWindow 는 계속 /api/chat 을 부른다
 * ② same-origin 유지 — HttpOnly 쿠키가 그대로 동작한다.
 *    프론트가 백엔드를 직접 부르면 크로스오리진이 되어 CORS 설정 + credentials
 *    옵션 + SameSite 완화가 줄줄이 따라온다. 쿠키 인증이 제일 먼저 깨진다.
 * ③ 엔드포인트 단위 점진 전환 — 한 파일씩 바꿔도 나머지는 TS 구현으로 계속 돈다
 */

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

// 백엔드로 넘길 헤더만 고른다.
// ★ 통째로 넘기면 안 된다 — host 는 백엔드가 자기 것으로 써야 하고,
//   accept-encoding 을 넘기면 압축된 응답을 그대로 다시 넘기다 깨질 수 있다.
const FORWARD_HEADERS = ["cookie", "authorization", "content-type"];

type ProxyOptions = {
  /**
   * 백엔드에 연결조차 못 했을 때 내려줄 JSON 의 키 이름.
   * chat 은 "reply" 여야 한다 — ChatWindow 가 data.reply 를 말풍선에 렌더하므로
   * 키가 다르면 빈 말풍선이 뜨고 사용자는 원인을 못 본다.
   */
  errorKey?: string;
};

export async function proxy(
  req: NextRequest,
  path: string,
  options: ProxyOptions = {}
): Promise<Response> {
  const headers = new Headers();
  for (const name of FORWARD_HEADERS) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }

  // 스트림을 그대로 넘기면 duplex 옵션이 필요해진다. 본문이 작은 JSON 이라
  // 텍스트로 읽어 넘기는 쪽이 단순하고 안전하다.
  const body = req.method === "GET" || req.method === "HEAD" ? undefined : await req.text();

  let upstream: Response;
  try {
    upstream = await fetch(`${BACKEND_URL}${path}`, {
      method: req.method,
      headers,
      body,
      cache: "no-store",
    });
  } catch {
    // 백엔드가 안 떠 있는 경우. 개발 중 제일 흔한 실패라 원인을 그대로 알린다.
    const key = options.errorKey ?? "error";
    return Response.json(
      { [key]: "⚠️ 백엔드 서버에 연결할 수 없습니다. (uvicorn 이 실행 중인지 확인해주세요)" },
      { status: 502 }
    );
  }

  const responseHeaders = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) responseHeaders.set("content-type", contentType);

  // ★ Set-Cookie 를 반드시 넘겨야 로그인이 성립한다.
  //   쿠키를 만드는 건 백엔드지만 브라우저에 저장시키는 건 이 응답이다.
  //   getSetCookie() 를 쓰는 이유 — 쿠키가 여러 개일 때 get() 은 콤마로 이어붙인
  //   문자열 하나를 주고, 그러면 브라우저가 파싱을 못 한다.
  for (const cookie of upstream.headers.getSetCookie()) {
    responseHeaders.append("set-cookie", cookie);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}
