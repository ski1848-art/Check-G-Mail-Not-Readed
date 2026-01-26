"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { 
  Users, 
  History, 
  LogOut, 
  Mail,
  Sun,
  Moon,
  Menu,
  X
} from "lucide-react";

interface NavigationProps {
  session: {
    user?: {
      email?: string | null;
      name?: string | null;
      image?: string | null;
    };
  };
}

export function Navigation({ session }: NavigationProps) {
  const pathname = usePathname();
  const [isDark, setIsDark] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    // 초기 다크모드 상태 확인
    const isDarkMode = localStorage.getItem("theme") === "dark" ||
      (!localStorage.getItem("theme") && window.matchMedia("(prefers-color-scheme: dark)").matches);
    setIsDark(isDarkMode);
    document.documentElement.classList.toggle("dark", isDarkMode);
  }, []);

  const toggleDarkMode = () => {
    const newDark = !isDark;
    setIsDark(newDark);
    document.documentElement.classList.toggle("dark", newDark);
    localStorage.setItem("theme", newDark ? "dark" : "light");
  };

  const navItems = [
    { href: "/users", label: "사용자 관리", icon: Users },
    { href: "/audit", label: "변경 이력", icon: History },
  ];

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <nav className="nav-glass">
      <div className="container mx-auto px-4">
        <div className="flex h-16 items-center justify-between">
          {/* 로고 */}
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent shadow-lg shadow-primary/20 group-hover:shadow-primary/30 transition-shadow">
                <Mail className="h-5 w-5 text-white" />
              </div>
              <span className="font-bold text-lg tracking-tight hidden sm:block">
                <span className="gradient-text">Notifier</span>
                <span className="text-muted-foreground ml-1">Admin</span>
              </span>
            </Link>

            {/* 데스크탑 네비게이션 */}
            <div className="hidden md:flex items-center gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`
                      flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium
                      transition-all duration-200
                      ${active 
                        ? "bg-primary/10 text-primary" 
                        : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                      }
                    `}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>

          {/* 우측 영역 */}
          <div className="flex items-center gap-3">
            {/* 다크모드 토글 */}
            <button
              onClick={toggleDarkMode}
              className="flex h-9 w-9 items-center justify-center rounded-xl 
                         text-muted-foreground hover:text-foreground hover:bg-secondary
                         transition-all duration-200"
              aria-label="Toggle dark mode"
            >
              {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>

            {/* 사용자 정보 */}
            <div className="hidden sm:flex items-center gap-3 pl-3 border-l border-border">
              <div className="text-right">
                <p className="text-sm font-medium text-foreground">
                  {session.user?.name || session.user?.email?.split("@")[0]}
                </p>
                <p className="text-xs text-muted-foreground">{session.user?.email}</p>
              </div>
              {session.user?.image && (
                <img
                  src={session.user.image}
                  alt="Profile"
                  className="h-9 w-9 rounded-full ring-2 ring-border"
                />
              )}
            </div>

            {/* 로그아웃 */}
            <Link
              href="/api/auth/signout"
              className="flex h-9 w-9 items-center justify-center rounded-xl
                         text-muted-foreground hover:text-destructive hover:bg-destructive/10
                         transition-all duration-200"
              title="로그아웃"
            >
              <LogOut className="h-5 w-5" />
            </Link>

            {/* 모바일 메뉴 버튼 */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="flex md:hidden h-9 w-9 items-center justify-center rounded-xl
                         text-muted-foreground hover:text-foreground hover:bg-secondary
                         transition-all duration-200"
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {/* 모바일 메뉴 */}
        {mobileMenuOpen && (
          <div className="md:hidden py-4 border-t border-border animate-fade-in">
            <div className="flex flex-col gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={`
                      flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium
                      transition-all duration-200
                      ${active 
                        ? "bg-primary/10 text-primary" 
                        : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                      }
                    `}
                  >
                    <Icon className="h-5 w-5" />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
