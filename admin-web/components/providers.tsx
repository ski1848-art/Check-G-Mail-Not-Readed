/**
 * providers.tsx - NextAuth 세션 프로바이더 (클라이언트 컴포넌트)
 * 
 * 모든 페이지에서 useSession() 훅을 사용할 수 있도록
 * SessionProvider로 앱 전체를 감싸는 래퍼 컴포넌트.
 */
"use client";

import { SessionProvider } from "next-auth/react";
import { ToastProvider } from "@/components/ui/toast";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <ToastProvider>{children}</ToastProvider>
    </SessionProvider>
  );
}
