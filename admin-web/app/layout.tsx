import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { getServerSession } from "next-auth";
import Link from "next/link";
import { Providers } from "@/components/providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Gmail Notifier Admin",
  description: "Management Console for Gmail Notifier",
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
          {session && (
            <nav className="sticky top-0 z-50 border-b border-gray-200 bg-white shadow-sm">
              <div className="container mx-auto px-6">
                <div className="flex h-16 items-center justify-between">
                  <div className="flex items-center gap-8">
                    <Link href="/" className="flex items-center gap-2">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 shadow-md text-white text-xl">
                        📧
                      </div>
                      <span className="text-lg font-bold text-gray-900">Notifier Admin</span>
                    </Link>
                    <div className="flex items-center gap-1">
                      <Link href="/users" className="px-3 py-2 text-sm font-medium text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors">
                        사용자
                      </Link>
                      <Link href="/events" className="px-3 py-2 text-sm font-medium text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors">
                        모니터링
                      </Link>
                      <Link href="/audit" className="px-3 py-2 text-sm font-medium text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors">
                        변경 이력
                      </Link>
                      <Link href="/settings" className="px-3 py-2 text-sm font-medium text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors">
                        시스템 설정
                      </Link>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-gray-600">{session.user?.email}</span>
                    <Link href="/api/auth/signout" className="text-sm text-gray-500 hover:text-red-600 transition-colors">
                      로그아웃
                    </Link>
                  </div>
                </div>
              </div>
            </nav>
          )}
          
          <main className="container mx-auto px-6 py-8">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
