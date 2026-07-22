/**
 * users/page.tsx - 사용자 관리 목록 페이지
 * 
 * [기능]
 *   - 등록된 모든 Slack 사용자 목록 표시 (Slack ID, 이름, Gmail 계정, 활성 상태)
 *   - 검색 필터 (Slack ID 또는 이름으로 검색)
 *   - 사용자 추가/편집 페이지로 이동
 * 
 * [데이터 소스] /api/routing-rules (GET)
 */
"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { Search, Mail, UserPlus, Users, Loader2 } from "lucide-react";

export default function UsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch("/api/routing-rules")
      .then(res => {
        if (res.status === 401) {
          window.location.href = "/login";
          return;
        }
        return res.json();
      })
      .then(data => {
        if (Array.isArray(data)) {
          setUsers(data);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Fetch error:", err);
        setLoading(false);
      });
  }, []);

  const filteredUsers = Array.isArray(users) ? users.filter(u => 
    u.slack_user_id.toLowerCase().includes(search.toLowerCase()) ||
    u.slack_display_name?.toLowerCase().includes(search.toLowerCase())
  ) : [];

  const activeCount = Array.isArray(users) ? users.filter(u => u.enabled).length : 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
          <p className="text-sm text-gray-600">불러오는 중...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">사용자 관리</h1>
          <p className="mt-1 text-sm text-gray-600">
            Gmail 알림을 받을 Slack 사용자를 관리합니다 · 총 {users.length}명 (활성: {activeCount}명)
          </p>
        </div>
        <Link href="/users/new" className="btn btn-primary">
          <UserPlus className="h-4 w-4" /> 사용자 추가
        </Link>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="사용자 검색..."
          className="input pl-10"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="card overflow-hidden">
        <table className="table">
          <thead>
            <tr>
              <th>사용자</th>
              <th>Gmail 계정</th>
              <th>상태</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.map((user) => (
              <tr key={user.id}>
                <td>
                  <div className="flex flex-col">
                    <span className="font-medium text-gray-900">
                      {user.slack_display_name || <span className="text-gray-400">-</span>}
                    </span>
                    <code className="mt-0.5 text-[11px] font-mono text-gray-400">
                      {user.slack_user_id}
                    </code>
                  </div>
                </td>
                <td>
                  <div className="space-y-1">
                    {user.gmail_accounts && user.gmail_accounts.length > 0 ? (
                      user.gmail_accounts.map((email: string, idx: number) => (
                        <div key={idx} className="inline-flex items-center gap-1 mr-1 mb-1 text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
                          <Mail className="h-3 w-3" /> {email}
                        </div>
                      ))
                    ) : (
                      <span className="text-xs text-gray-400">등록 안됨</span>
                    )}
                  </div>
                </td>
                <td>
                  {user.enabled ? (
                    <span className="badge badge-success">
                      ● 활성
                    </span>
                  ) : (
                    <span className="badge badge-gray">
                      ● 비활성
                    </span>
                  )}
                </td>
                <td className="text-right">
                  <Link href={`/users/${user.slack_user_id}`} className="inline-flex min-h-[40px] items-center gap-1 px-2 text-sm font-medium text-blue-600 hover:text-blue-800">
                    편집 →
                  </Link>
                </td>
              </tr>
            ))}
            {filteredUsers.length === 0 && (
              <tr>
                <td colSpan={4} className="py-16 text-center">
                  <Users className="mx-auto mb-4 h-10 w-10 text-gray-300" />
                  <p className="text-sm font-medium text-gray-600">등록된 사용자가 없습니다</p>
                  <p className="mt-1 text-xs text-gray-500">새 사용자를 추가해보세요</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
