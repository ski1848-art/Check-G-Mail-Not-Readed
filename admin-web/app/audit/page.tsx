/**
 * audit/page.tsx - 변경 이력(감사 로그) 페이지
 * 
 * [표시 정보]
 *   - 액션 유형 (생성/수정/삭제) 배지
 *   - 대상 Slack User ID
 *   - 실행자 이메일, 시간
 *   - 상세 정보 (JSON 펼치기)
 * 
 * [데이터 소스] /api/audit-logs (GET, 최근 200건)
 */
"use client";
import { useState, useEffect } from "react";
import { ScrollText, User, Clock, Code2 } from "lucide-react";

export default function AuditPage() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/audit-logs")
      .then(res => res.json())
      .then(data => {
        setLogs(data);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex items-center gap-3">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent"></div>
          <p className="text-sm text-gray-600">불러오는 중...</p>
        </div>
      </div>
    );
  }

  const getActionBadge = (action: string) => {
    switch (action) {
      case "CREATE":
        return <span className="badge badge-success">생성</span>;
      case "UPDATE":
        return <span className="badge badge-info">수정</span>;
      case "DELETE":
        return <span className="badge badge-danger">삭제</span>;
      case "UPDATE_SYSTEM_SETTINGS":
        return <span className="badge badge-info">설정 변경</span>;
      case "DELETE_PREFERENCE":
        return <span className="badge badge-warning">차단 해제</span>;
      case "MANUAL_NOTIFICATION_TRIGGER":
        return <span className="badge badge-success">수동 알림 전송</span>;
      case "MANUAL_NOTIFICATION_BLOCK":
        return <span className="badge badge-danger">수동 차단</span>;
      default:
        return <span className="badge badge-gray">{action}</span>;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">변경 이력</h1>
        <p className="mt-1 text-sm text-gray-600">
          모든 설정 변경 사항을 확인할 수 있습니다 · 총 {logs.length}건
        </p>
      </div>

      {logs.length === 0 ? (
        <div className="card p-16 text-center">
          <ScrollText className="mx-auto mb-4 h-12 w-12 text-gray-300" />
          <p className="text-sm font-medium text-gray-600">기록된 변경 이력이 없습니다</p>
        </div>
      ) : (
        <div className="space-y-3">
          {logs.map((log) => (
            <div key={log.id} className="card p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div className="space-y-2">
                  <div className="flex items-center gap-3">
                    {getActionBadge(log.action)}
                    <code className="rounded bg-gray-100 px-2 py-1 text-xs font-mono text-gray-700">
                      {log.target_slack_user_id}
                    </code>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <User className="h-3.5 w-3.5" /> {log.actor_email}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" /> {log.created_at
                        ? new Date(log.created_at._seconds * 1000).toLocaleString("ko-KR", {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "-"}
                    </span>
                  </div>
                </div>
              </div>
              {log.after && (
                <details className="mt-3 group">
                  <summary className="cursor-pointer text-xs text-blue-600 hover:text-blue-800 font-medium">
                    상세 정보 보기
                  </summary>
                  <div className="mt-2 overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
                    <div className="flex items-center gap-1.5 border-b border-gray-200 bg-gray-100 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                      <Code2 className="h-3 w-3" /> 기술 상세
                    </div>
                    <pre className="overflow-x-auto p-3 text-xs text-gray-600">
                      {JSON.stringify(log.after, null, 2)}
                    </pre>
                  </div>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
