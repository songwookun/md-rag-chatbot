"use client";

import { useState } from "react";

// 앱 이름은 .env의 NEXT_PUBLIC_APP_NAME으로 변경 (기본: AXBrain)
const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || "AXBrain";

export default function LoginScreen({
  onSuccess,
}: {
  onSuccess: () => void;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const res = await fetch("/api/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });

    if (res.ok) {
      onSuccess();
    } else {
      setError("비밀번호가 틀렸습니다.");
    }
    setLoading(false);
  };

  return (
    <div className="flex items-center justify-center min-h-screen">
      <form
        onSubmit={handleSubmit}
        className="bg-white dark:bg-gray-900 p-8 rounded-2xl shadow-lg w-80 space-y-4"
      >
        <h1 className="text-xl font-bold text-center text-gray-900 dark:text-gray-100">{APP_NAME}</h1>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="비밀번호 입력"
          className="w-full px-4 py-3 bg-gray-100 dark:bg-gray-800 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
          autoFocus
        />
        {error && <p className="text-red-400 text-sm text-center">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium disabled:opacity-50"
        >
          {loading ? "확인 중..." : "로그인"}
        </button>
      </form>
    </div>
  );
}
