/**
 * layout.tsx - 루트 레이아웃 (서버 컴포넌트)
 * 
 * [역할]
 *   - 전체 앱의 HTML 구조 및 글로벌 스타일 적용
 *   - 로그인된 사용자에게만 상단 네비게이션 바 표시
 *   - SessionProvider로 클라이언트 세션 관리
 * 
 * [네비게이션 메뉴]
 *   사용자 | 모니터링 | 변경 이력 | 시스템 설정
 */
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { getServerSession } from "next-auth";
import { Providers } from "@/components/providers";
import { Navigation } from "@/app/components/Navigation";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Gmail Notifier 관리자",
  description: "Gmail Notifier 관리 콘솔",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const session = await getServerSession();

  return (
    <html lang="ko">
      <body className={inter.className}>
        <Providers>
          {session && <Navigation session={session} />}
          <main className="container mx-auto px-6 py-8">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
