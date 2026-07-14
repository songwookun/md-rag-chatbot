import type { Metadata } from "next";
import "./globals.css";

// 앱 이름은 .env의 NEXT_PUBLIC_APP_NAME으로 변경 (기본: AXBrain)
const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || "AXBrain";

export const metadata: Metadata = {
  title: APP_NAME,
  description: "AI 지식 수집 & RAG 챗봇",
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                const theme = localStorage.getItem('theme') || 'dark';
                document.documentElement.setAttribute('data-theme', theme);
              })();
            `,
          }}
        />
      </head>
      <body className="bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 min-h-screen transition-colors">
        {children}
      </body>
    </html>
  );
}
