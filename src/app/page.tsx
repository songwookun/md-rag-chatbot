"use client";

import { useState, useEffect } from "react";
import LoginScreen from "@/components/LoginScreen";
import ChatWindow from "@/components/ChatWindow";

export default function Home() {
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    // 서버에 인증 상태 확인
    fetch("/api/auth/check")
      .then((res) => {
        if (res.ok) setAuthenticated(true);
      })
      .finally(() => setChecking(false));
  }, []);

  if (checking) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-400">로딩 중...</div>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <LoginScreen
        onSuccess={() => {
          setAuthenticated(true);
        }}
      />
    );
  }

  return <ChatWindow />;
}
