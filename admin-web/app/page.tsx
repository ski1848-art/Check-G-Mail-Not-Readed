"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";

interface Stats {
  totalUsers: number;
  activeUsers: number;
  totalProcessedToday: number;
  notifiedToday: number;
  silencedToday: number;
  systemStatus: string;
}

interface CostStats {
  period: string;
  totalCalls: number;
  totalEvents: number;
  tokens: {
    input: number;
    output: number;
    cacheRead: number;
    cacheWrite: number;
  };
  cost: {
    input: number;
    output: number;
    cacheRead: number;
    cacheWrite: number;
    totalUSD: number;
    totalKRW: number;
  };
  cacheHitRate: number;
  dailyBreakdown: Array<{
    date: string;
    calls: number;
    cost: number;
  }>;
  note: string;
}

interface SystemStatus {
  enabled: boolean;
  pausedAt: string | null;
  pausedBy: string | null;
  pauseReason: string | null;
  dailyLimitCalls: number;
  dailyLimitCostUsd: number;
  lastBatchAt: string | null;
  lastBatchProcessed: number;
  todayUsage: {
    date: string;
    calls: number;
    costUsd: number;
    inputTokens: number;
    outputTokens: number;
  };
}

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [stats, setStats] = useState<Stats | null>(null);
  const [costStats, setCostStats] = useState<CostStats | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchSystemStatus = async () => {
    try {
      const res = await fetch("/api/system");
      if (res.ok) {
        const data = await res.json();
        setSystemStatus(data);
      }
    } catch (err) {
      console.error("Failed to fetch system status:", err);
    }
  };

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
    } else if (status === "authenticated") {
      // 기존 통계, 비용 통계, 시스템 상태를 병렬로 가져오기
      Promise.all([
        fetch("/api/stats").then(res => res.json()),
        fetch("/api/stats/cost").then(res => res.json()),
        fetch("/api/system").then(res => res.ok ? res.json() : null)
      ])
        .then(([statsData, costData, sysData]) => {
          setStats(statsData);
          setCostStats(costData);
          setSystemStatus(sysData);
          setLoading(false);
        })
        .catch(err => {
          console.error("Failed to fetch stats:", err);
          setLoading(false);
        });
    }
  }, [status, router]);

  const handleSystemAction = async (action: string) => {
    setActionLoading(action);
    try {
      const res = await fetch("/api/system", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      
      const data = await res.json();
      
      if (res.ok) {
        alert(data.message);
        fetchSystemStatus();
      } else {
        alert(data.message || "오류가 발생했습니다.");
      }
    } catch (err) {
      console.error("Action failed:", err);
      alert("요청 실패. 네트워크를 확인하세요.");
    } finally {
      setActionLoading(null);
    }
  };

  if (status === "loading" || loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">대시보드</h1>
        <p className="text-gray-600">Gmail Notifier 서비스의 현재 상태를 확인합니다.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Stat Cards */}
        <div className="card p-6 border-l-4 border-blue-600">
          <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">전체 사용자</p>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-gray-900">{stats?.totalUsers || 0}</span>
            <span className="text-sm text-gray-500">명 등록됨</span>
          </div>
          <p className="mt-2 text-xs text-blue-600 font-medium">활성 사용자: {stats?.activeUsers || 0}명</p>
        </div>

        <div className="card p-6 border-l-4 border-green-600">
          <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">오늘 보낸 알림</p>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-gray-900">{stats?.notifiedToday || 0}</span>
            <span className="text-sm text-gray-500">건 발송</span>
          </div>
          <p className="mt-2 text-xs text-green-600 font-medium">전체 처리 중 {(stats?.notifiedToday || 0) / (stats?.totalProcessedToday || 1) * 100 | 0}%</p>
        </div>

        <div className="card p-6 border-l-4 border-amber-600">
          <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">오늘 무시된 메일</p>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-gray-900">{stats?.silencedToday || 0}</span>
            <span className="text-sm text-gray-500">건 제외</span>
          </div>
          <p className="mt-2 text-xs text-amber-600 font-medium">노이즈 필터링 정상 작동 중</p>
        </div>

        <div className="card p-6 border-l-4 border-purple-600">
          <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">시스템 상태</p>
          <div className="flex items-center gap-2 mt-2">
            <span className="h-3 w-3 rounded-full bg-green-500 animate-pulse"></span>
            <span className="text-2xl font-bold text-gray-900">{stats?.systemStatus}</span>
          </div>
          <p className="mt-2 text-xs text-gray-500">Cloud Run & Firestore 연결됨</p>
        </div>
      </div>

      {/* 🎛️ 시스템 제어 리모컨 */}
      {systemStatus && (
        <div className={`card p-6 border-2 ${systemStatus.enabled ? 'border-green-200 bg-green-50/50' : 'border-red-200 bg-red-50/50'}`}>
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            {/* 상태 표시 */}
            <div className="flex items-center gap-4">
              <div className={`w-16 h-16 rounded-2xl flex items-center justify-center text-3xl ${
                systemStatus.enabled ? 'bg-green-100' : 'bg-red-100'
              }`}>
                {systemStatus.enabled ? '✅' : '⏸️'}
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                  🎛️ 시스템 제어
                  <span className={`text-sm font-medium px-2 py-0.5 rounded-full ${
                    systemStatus.enabled 
                      ? 'bg-green-100 text-green-700' 
                      : 'bg-red-100 text-red-700'
                  }`}>
                    {systemStatus.enabled ? '실행 중' : '일시 중지'}
                  </span>
                </h2>
                {systemStatus.enabled ? (
                  <p className="text-sm text-gray-600">
                    마지막 배치: {systemStatus.lastBatchAt 
                      ? new Date(systemStatus.lastBatchAt).toLocaleString('ko-KR') 
                      : '없음'} 
                    ({systemStatus.lastBatchProcessed}건 처리)
                  </p>
                ) : (
                  <div className="text-sm text-red-600">
                    <p>중지 시간: {systemStatus.pausedAt ? new Date(systemStatus.pausedAt).toLocaleString('ko-KR') : '-'}</p>
                    <p>사유: {systemStatus.pauseReason || '-'}</p>
                    <p>중지자: {systemStatus.pausedBy || '-'}</p>
                  </div>
                )}
              </div>
            </div>

            {/* 제어 버튼들 */}
            <div className="flex flex-col sm:flex-row gap-3">
              {systemStatus.enabled ? (
                <>
                  <button
                    onClick={() => handleSystemAction("pause")}
                    disabled={actionLoading === "pause"}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 font-medium flex items-center gap-2 transition-colors"
                  >
                    {actionLoading === "pause" ? (
                      <span className="animate-spin">⏳</span>
                    ) : (
                      <>⏸️ 일시 중지</>
                    )}
                  </button>
                  <button
                    onClick={() => handleSystemAction("run_batch")}
                    disabled={actionLoading === "run_batch"}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium flex items-center gap-2 transition-colors"
                  >
                    {actionLoading === "run_batch" ? (
                      <span className="animate-spin">⏳</span>
                    ) : (
                      <>🔄 수동 실행</>
                    )}
                  </button>
                </>
              ) : (
                <button
                  onClick={() => handleSystemAction("resume")}
                  disabled={actionLoading === "resume"}
                  className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 font-bold text-lg flex items-center gap-2 transition-colors shadow-lg"
                >
                  {actionLoading === "resume" ? (
                    <span className="animate-spin">⏳</span>
                  ) : (
                    <>▶️ 시스템 재시작</>
                  )}
                </button>
              )}
            </div>
          </div>

          {/* 일일 한도 표시 */}
          <div className="mt-4 pt-4 border-t border-gray-200 grid grid-cols-2 gap-4">
            <div className="bg-white/70 rounded-lg p-3">
              <div className="text-xs text-gray-500 uppercase">오늘 AI 호출</div>
              <div className="text-lg font-bold text-gray-900">
                {systemStatus.todayUsage.calls} / {systemStatus.dailyLimitCalls}
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
                <div 
                  className={`h-1.5 rounded-full ${
                    systemStatus.todayUsage.calls / systemStatus.dailyLimitCalls > 0.8 
                      ? 'bg-red-500' 
                      : 'bg-green-500'
                  }`}
                  style={{ width: `${Math.min(systemStatus.todayUsage.calls / systemStatus.dailyLimitCalls * 100, 100)}%` }}
                />
              </div>
            </div>
            <div className="bg-white/70 rounded-lg p-3">
              <div className="text-xs text-gray-500 uppercase">오늘 비용</div>
              <div className="text-lg font-bold text-gray-900">
                ${systemStatus.todayUsage.costUsd.toFixed(2)} / ${systemStatus.dailyLimitCostUsd}
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
                <div 
                  className={`h-1.5 rounded-full ${
                    systemStatus.todayUsage.costUsd / systemStatus.dailyLimitCostUsd > 0.8 
                      ? 'bg-red-500' 
                      : 'bg-green-500'
                  }`}
                  style={{ width: `${Math.min(systemStatus.todayUsage.costUsd / systemStatus.dailyLimitCostUsd * 100, 100)}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* AI 비용 모니터링 섹션 */}
      {costStats && (
        <div className="card p-6 bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-200">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                💰 AI 비용 모니터링
                <span className="text-sm font-normal text-gray-500">({costStats.period})</span>
              </h2>
              <p className="text-xs text-amber-600 mt-1">⚠️ {costStats.note}</p>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-indigo-700">
                ₩{costStats.cost.totalKRW.toLocaleString()}
              </div>
              <div className="text-sm text-gray-500">${costStats.cost.totalUSD.toFixed(2)} USD</div>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white/70 rounded-lg p-3">
              <div className="text-xs text-gray-500 uppercase">AI 호출</div>
              <div className="text-xl font-bold text-gray-900">{costStats.totalCalls.toLocaleString()}건</div>
            </div>
            <div className="bg-white/70 rounded-lg p-3">
              <div className="text-xs text-gray-500 uppercase">입력 토큰</div>
              <div className="text-xl font-bold text-gray-900">{(costStats.tokens.input / 1_000_000).toFixed(2)}M</div>
              <div className="text-xs text-gray-400">${costStats.cost.input.toFixed(2)}</div>
            </div>
            <div className="bg-white/70 rounded-lg p-3">
              <div className="text-xs text-gray-500 uppercase">출력 토큰</div>
              <div className="text-xl font-bold text-gray-900">{(costStats.tokens.output / 1_000_000).toFixed(2)}M</div>
              <div className="text-xs text-gray-400">${costStats.cost.output.toFixed(2)}</div>
            </div>
            <div className="bg-white/70 rounded-lg p-3">
              <div className="text-xs text-gray-500 uppercase">캐시 적중률</div>
              <div className="text-xl font-bold text-green-600">{costStats.cacheHitRate}%</div>
              <div className="text-xs text-gray-400">프롬프트 캐싱</div>
            </div>
          </div>

          {/* 일별 비용 막대 차트 */}
          {costStats.dailyBreakdown.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3">일별 AI 호출 추이</h3>
              <div className="flex items-end gap-1 h-24 bg-white/50 rounded-lg p-2">
                {costStats.dailyBreakdown.slice(-14).map((day, idx) => {
                  const maxCalls = Math.max(...costStats.dailyBreakdown.map(d => d.calls));
                  const heightPercent = maxCalls > 0 ? (day.calls / maxCalls) * 100 : 0;
                  return (
                    <div
                      key={idx}
                      className="flex-1 bg-indigo-400 hover:bg-indigo-600 rounded-t transition-colors cursor-pointer group relative"
                      style={{ height: `${Math.max(heightPercent, 4)}%` }}
                      title={`${day.date}: ${day.calls}건, $${day.cost.toFixed(2)}`}
                    >
                      <div className="hidden group-hover:block absolute bottom-full left-1/2 -translate-x-1/2 mb-1 bg-gray-900 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
                        {day.date.slice(5)}: {day.calls}건
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>{costStats.dailyBreakdown.slice(-14)[0]?.date.slice(5)}</span>
                <span>{costStats.dailyBreakdown.slice(-1)[0]?.date.slice(5)}</span>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Quick Actions */}
        <div className="card p-6 space-y-4">
          <h2 className="text-xl font-bold text-gray-900">빠른 작업</h2>
          <div className="grid grid-cols-2 gap-4">
            <Link href="/users/new" className="flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-all group">
              <span className="text-2xl mb-2 group-hover:scale-110 transition-transform">👤</span>
              <span className="text-sm font-semibold">새 사용자 추가</span>
            </Link>
            <Link href="/events" className="flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-all group">
              <span className="text-2xl mb-2 group-hover:scale-110 transition-transform">🔍</span>
              <span className="text-sm font-semibold">실시간 모니터링</span>
            </Link>
            <Link href="/audit" className="flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-all group">
              <span className="text-2xl mb-2 group-hover:scale-110 transition-transform">📜</span>
              <span className="text-sm font-semibold">변경 이력 확인</span>
            </Link>
            <Link href="/settings" className="flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-all group">
              <span className="text-2xl mb-2 group-hover:scale-110 transition-transform">⚙️</span>
              <span className="text-sm font-semibold">시스템 설정</span>
            </Link>
          </div>
        </div>

        {/* System Info */}
        <div className="card p-6 bg-gray-900 text-white">
          <h2 className="text-xl font-bold mb-4">서비스 정보</h2>
          <div className="space-y-4 text-sm text-gray-400">
            <div className="flex justify-between border-b border-gray-800 pb-2">
              <span>서비스 이름</span>
              <span className="text-gray-100 font-mono">Gmail Important Notifier</span>
            </div>
            <div className="flex justify-between border-b border-gray-800 pb-2">
              <span>버전</span>
              <span className="text-gray-100 font-mono">v1.2.0 (Next.js 14)</span>
            </div>
            <div className="flex justify-between border-b border-gray-800 pb-2">
              <span>최근 스케줄 실행</span>
              <span className="text-gray-100 font-mono">5분 주기</span>
            </div>
            <div className="flex justify-between border-b border-gray-800 pb-2">
              <span>AI 엔진</span>
              <span className="text-gray-100 font-mono">AWS Bedrock (Claude 3.5 Haiku)</span>
            </div>
            <div className="pt-4 text-xs text-gray-500">
              * 데이터는 Firestore에서 실시간으로 집계됩니다.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
