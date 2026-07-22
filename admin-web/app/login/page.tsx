/**
 * login/page.tsx - 로그인 페이지
 * 
 * Google OAuth 로그인 버튼만 제공.
 * 로그인 성공 시 대시보드(/)로 리다이렉트.
 * Google Workspace 관리자 계정만 접근 가능 (NextAuth signIn 콜백에서 검증).
 */
"use client";
import { signIn } from "next-auth/react";
import { Mail } from "lucide-react";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 via-white to-blue-50 p-6">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center space-y-3">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
            <Mail className="h-8 w-8" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900">Notifier Admin</h1>
          <p className="text-sm text-gray-600">Gmail 알림 서비스 관리 콘솔</p>
        </div>

        <div className="card p-8 shadow-lg space-y-6">
          <div className="space-y-2 text-center">
            <h2 className="text-xl font-bold text-gray-900">로그인</h2>
            <p className="text-sm text-gray-600">Google 계정으로 계속하기</p>
          </div>

          <button
            onClick={() => signIn("google", { callbackUrl: "/" })}
            className="w-full flex items-center justify-center gap-3 rounded-lg border-2 border-gray-200 bg-white px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-all shadow-sm hover:shadow"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Google 계정으로 로그인
          </button>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200"></div>
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-white px-2 text-gray-500">Google Workspace 관리자 계정 필요</span>
            </div>
          </div>

          <p className="text-center text-xs text-gray-500">
            승인된 관리자만 접근 가능합니다
          </p>
        </div>

        <p className="text-center text-xs text-gray-500">
          © 2026 Gmail Notifier. All rights reserved.
        </p>
      </div>
    </div>
  );
}
