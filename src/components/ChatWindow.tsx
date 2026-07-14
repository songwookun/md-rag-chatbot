"use client";

import { useState, useRef, useEffect } from "react";
import MessageBubble from "./MessageBubble";

export interface Message {
  role: "user" | "assistant";
  content: string;
}

// 앱 이름은 .env의 NEXT_PUBLIC_APP_NAME으로 변경 (기본: AXBrain)
const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || "AXBrain";

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: `안녕하세요! ${APP_NAME}입니다.\n\n저장 - URL이나 텍스트를 보내면 자동 요약 후 저장\n질문 - 저장된 노트에 대해 질문하면 RAG로 답변`,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isDark, setIsDark] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const theme = localStorage.getItem("theme") || "dark";
    setIsDark(theme === "dark");
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const toggleTheme = () => {
    const newTheme = isDark ? "light" : "dark";
    setIsDark(!isDark);
    localStorage.setItem("theme", newTheme);
    document.documentElement.setAttribute("data-theme", newTheme);
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      if (res.status === 401) {
        window.location.reload();
        return;
      }

      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "오류가 발생했습니다. 다시 시도해주세요." },
      ]);
    }

    setLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <h1 className="text-lg font-bold">{APP_NAME}</h1>
        <button
          onClick={toggleTheme}
          className="relative w-12 h-6 rounded-full transition-colors duration-300 bg-gray-300 dark:bg-gray-600"
          title={isDark ? "라이트 모드" : "다크 모드"}
        >
          <span
            className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300 ${
              isDark ? "translate-x-6" : "translate-x-0"
            }`}
          />
        </button>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-gray-400 text-sm">
            <div className="animate-pulse">정리하는 중...</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-800">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="링크/정보 저장 또는 질문을 입력하세요..."
            rows={1}
            className="flex-1 px-4 py-3 bg-gray-100 dark:bg-gray-800 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="px-5 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium disabled:opacity-50"
          >
            전송
          </button>
        </div>
      </div>
    </div>
  );
}
