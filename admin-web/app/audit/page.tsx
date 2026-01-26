"use client";

import { useEffect, useState } from "react";

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
          <div className="text-5xl mb-4">📋</div>
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
                      👤 {log.actor_email}
                    </span>
                    <span className="flex items-center gap-1">
                      🕐 {log.created_at 
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
                  <pre className="mt-2 rounded-lg bg-gray-50 p-3 text-xs text-gray-600 overflow-x-auto border border-gray-200">
                    {JSON.stringify(log.after, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
