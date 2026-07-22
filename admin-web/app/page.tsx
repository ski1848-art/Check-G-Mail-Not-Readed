/**
 * page.tsx (/) - 대시보드 메인 페이지
 *
 * [레이아웃 — 운영 콘솔 중심]
 *   1. Hero 운영 콘솔: (좌) 시스템 상태 + 제어 버튼, (우) 오늘 AI 사용량 + 위험도(안전/주의/위험)
 *   2. 오늘의 운영 요약: 전체 사용자 / 오늘 알림 / 오늘 무시
 *   3. 이번 달 AI 비용: 월 누적 비용·지표(좌) + 일별 추이 차트(우)
 *   4. 빠른 작업 + 서비스 정보
 *
 * [데이터 소스]
 *   /api/stats, /api/stats/cost, /api/system 을 병렬 호출
 *   ※ 위험도(riskRatio)는 기존 데이터로 계산하는 표시 전용 파생값 — 동작/데이터/API 불변
 */
"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { useToast } from "@/components/ui/toast";
import { AlertTriangle, CheckCircle2, PauseCircle, PlayCircle, RefreshCw, Loader2, Wallet, UserPlus, Search, ScrollText, Settings } from "lucide-react";

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
  const { toast } = useToast();
  const [stats, setStats] = useState<Stats | null>(null);
  const [costStats, setCostStats] = useState<CostStats | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<{ action: string; title: string; message: string } | null>(null);
  const [loadError, setLoadError] = useState(false);

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
        fetch("/api/stats").then(res => res.ok ? res.json() : Promise.reject(new Error("stats"))),
        fetch("/api/stats/cost").then(res => res.ok ? res.json() : Promise.reject(new Error("cost"))),
        fetch("/api/system").then(res => res.ok ? res.json() : null)
      ])
        .then(([statsData, costData, sysData]) => {
          setStats(statsData);
          setCostStats(costData);
          setSystemStatus(sysData);
          setLoadError(false);
          setLoading(false);
        })
        .catch(err => {
          console.error("Failed to fetch stats:", err);
          setLoadError(true);
          setLoading(false);
        });
    }
  }, [status, router]);

  useEffect(() => {
    if (!pendingAction) return;
    const onEsc = (e: KeyboardEvent) => { if (e.key === "Escape") setPendingAction(null); };
    document.addEventListener("keydown", onEsc);
    return () => document.removeEventListener("keydown", onEsc);
  }, [pendingAction]);

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
        toast(data.message, "success");
        fetchSystemStatus();
      } else {
        toast(data.message || "오류가 발생했습니다.", "error");
      }
    } catch (err) {
      console.error("Action failed:", err);
      toast("요청 실패. 네트워크를 확인하세요.", "error");
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

  // ── 표시 전용 파생값(동작·데이터·API 불변): 오늘 사용량의 하루 한도 대비 위험도 ──
  // 기존 systemStatus 값만으로 계산하는 순수 표현용 값. 안전/주의/위험 색 큐에만 사용.
  const callRatio = systemStatus && systemStatus.dailyLimitCalls > 0
    ? systemStatus.todayUsage.calls / systemStatus.dailyLimitCalls : 0;
  const costRatio = systemStatus && systemStatus.dailyLimitCostUsd > 0
    ? systemStatus.todayUsage.costUsd / systemStatus.dailyLimitCostUsd : 0;
  const riskRatio = Math.max(callRatio, costRatio);
  const riskLevel = riskRatio >= 0.9 ? "danger" : riskRatio >= 0.7 ? "warn" : "safe";
  const riskLabel = riskLevel === "danger" ? "위험" : riskLevel === "warn" ? "주의" : "안전";
  const riskText = riskLevel === "danger" ? "text-red-600" : riskLevel === "warn" ? "text-amber-600" : "text-blue-600";
  const riskBar = riskLevel === "danger" ? "bg-red-500" : riskLevel === "warn" ? "bg-amber-500" : "bg-blue-500";
  const riskBadge = riskLevel === "danger" ? "bg-red-100 text-red-700" : riskLevel === "warn" ? "bg-amber-100 text-amber-700" : "bg-blue-100 text-blue-700";
  const heroBorder = systemStatus == null ? "border-amber-200" : systemStatus.enabled ? "border-blue-100" : "border-red-200";
  const costBorder = riskLevel === "danger" ? "border-red-200" : riskLevel === "warn" ? "border-amber-200" : "border-blue-100";

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {pendingAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" onClick={() => setPendingAction(null)}>
          <div role="dialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-msg" className="card p-6 max-w-md w-full" onClick={(e) => e.stopPropagation()}>
            <h3 id="confirm-title" className="text-lg font-bold text-gray-900">{pendingAction.title}</h3>
            <p id="confirm-msg" className="mt-2 text-sm text-gray-600">{pendingAction.message}</p>
            <div className="mt-6 flex justify-end gap-3">
              <button onClick={() => setPendingAction(null)} className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium transition-colors">취소</button>
              <button onClick={() => { const a = pendingAction.action; setPendingAction(null); handleSystemAction(a); }} className="btn btn-primary">확인</button>
            </div>
          </div>
        </div>
      )}
      {loadError && (
        <div role="alert" className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <span className="flex items-center gap-1.5 text-sm font-medium text-red-700">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" /> 일부 정보를 불러오지 못했습니다. 아래 숫자가 실제와 다를 수 있습니다.
          </span>
          <button onClick={() => window.location.reload()} className="text-sm font-semibold text-red-700 underline hover:text-red-800">새로고침</button>
        </div>
      )}

      <div>
        <h1 className="text-2xl font-bold text-gray-900">대시보드</h1>
        <p className="text-sm text-gray-600">Gmail Notifier 서비스 현황을 한눈에 확인합니다.</p>
      </div>

      {/* ===== Hero: 운영 콘솔 ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* 좌: 시스템 상태 + 제어 */}
        <div className={`card border-2 ${heroBorder} p-6 lg:p-8 lg:col-span-8`}>
          {systemStatus == null ? (
            <div className="flex items-center gap-3 text-amber-700">
              <AlertTriangle className="h-6 w-6 flex-shrink-0" />
              <div>
                <p className="text-lg font-bold">상태를 불러오지 못했습니다</p>
                <button onClick={() => window.location.reload()} className="text-sm text-amber-700 underline hover:text-amber-800">새로고침</button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-6">
              {/* 큰 상태 표시 */}
              <div className="flex items-center gap-4">
                <div className={`w-14 h-14 rounded-2xl flex items-center justify-center shrink-0 ${systemStatus.enabled ? 'bg-blue-50' : 'bg-red-100'}`}>
                  {systemStatus.enabled ? (
                    <CheckCircle2 className="h-8 w-8 text-blue-600" />
                  ) : (
                    <PauseCircle className="h-8 w-8 text-red-600" />
                  )}
                </div>
                <div>
                  <p className="text-sm text-gray-500">시스템 상태</p>
                  <p className={`text-3xl font-bold ${systemStatus.enabled ? 'text-gray-900' : 'text-red-600'}`}>
                    {systemStatus.enabled ? '정상 실행 중' : '일시 중지됨'}
                  </p>
                  {systemStatus.enabled ? (
                    <p className="mt-1 text-sm text-gray-500">
                      마지막 실행: {systemStatus.lastBatchAt
                        ? new Date(systemStatus.lastBatchAt).toLocaleString('ko-KR')
                        : '-'} ({systemStatus.lastBatchProcessed}건 처리)
                    </p>
                  ) : (
                    <div className="mt-1 text-sm text-red-600">
                      <p>사유: {systemStatus.pauseReason || '-'}</p>
                      <p>중지: {systemStatus.pausedAt ? new Date(systemStatus.pausedAt).toLocaleString('ko-KR') : '-'} · {systemStatus.pausedBy || '-'}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* 제어 버튼 (중지 시 재시작 버튼이 가장 크게) */}
              <div className="flex flex-col sm:flex-row gap-2 shrink-0">
                {systemStatus.enabled ? (
                  <>
                    <button
                      onClick={() => setPendingAction({ action: "pause", title: "전체 알림을 일시 중지할까요?", message: "모든 사용자에게 가는 Gmail 알림 발송이 멈춥니다. 다시 시작하기 전까지 알림이 오지 않습니다." })}
                      disabled={actionLoading === "pause"}
                      className="btn btn-danger disabled:opacity-50"
                    >
                      {actionLoading === "pause" ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <><PauseCircle className="h-4 w-4" /> 일시 중지</>
                      )}
                    </button>
                    <button
                      onClick={() => setPendingAction({ action: "run_batch", title: "지금 수동으로 실행할까요?", message: "즉시 메일을 조회해 분류·알림을 실행합니다. 이미 처리된 메일은 중복 알림되지 않습니다." })}
                      disabled={actionLoading === "run_batch"}
                      className="btn btn-primary disabled:opacity-50"
                    >
                      {actionLoading === "run_batch" ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <><RefreshCw className="h-4 w-4" /> 수동 실행</>
                      )}
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => handleSystemAction("resume")}
                    disabled={actionLoading === "resume"}
                    className="btn btn-primary text-base px-6 py-3 disabled:opacity-50"
                  >
                    {actionLoading === "resume" ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <><PlayCircle className="h-5 w-5" /> 시스템 재시작</>
                    )}
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 우: 오늘 AI 사용량 + 위험도 */}
        <div className={`card border-2 ${costBorder} p-6 lg:col-span-4`}>
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500 flex items-center gap-1.5"><Wallet className="h-4 w-4" /> 오늘 AI 사용</p>
            {systemStatus && (
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${riskBadge}`}>{riskLabel}</span>
            )}
          </div>
          {systemStatus ? (
            <>
              <p className={`mt-2 text-3xl font-bold ${riskText}`}>${systemStatus.todayUsage.costUsd.toFixed(2)}</p>
              <p className="text-xs text-gray-500">하루 한도 ${systemStatus.dailyLimitCostUsd} 대비</p>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                <div className={`h-2 rounded-full ${riskBar}`} style={{ width: `${Math.min(costRatio * 100, 100)}%` }} />
              </div>
              <div className="mt-3">
                <p className="text-xs text-gray-500">AI 호출 {systemStatus.todayUsage.calls} / {systemStatus.dailyLimitCalls}건</p>
                <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
                  <div
                    className={`h-1.5 rounded-full ${callRatio >= 0.9 ? 'bg-red-500' : callRatio >= 0.7 ? 'bg-amber-500' : 'bg-blue-500'}`}
                    style={{ width: `${Math.min(callRatio * 100, 100)}%` }}
                  />
                </div>
              </div>
            </>
          ) : (
            <p className="mt-2 text-sm text-gray-400">사용량 정보를 불러오지 못했습니다.</p>
          )}
        </div>
      </div>

      {/* ===== 오늘의 운영 요약 ===== */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">전체 사용자</p>
          <p className="mt-1 text-3xl font-bold text-gray-900">{stats?.totalUsers || 0}<span className="ml-1 text-sm font-normal text-gray-500">명</span></p>
          <p className="mt-1 text-xs text-gray-500">활성 사용자 {stats?.activeUsers || 0}명</p>
        </div>
        <div className="card p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">오늘 보낸 알림</p>
          <p className="mt-1 text-3xl font-bold text-gray-900">{stats?.notifiedToday || 0}<span className="ml-1 text-sm font-normal text-gray-500">건</span></p>
          <p className="mt-1 text-xs text-gray-500">전체 처리 중 {(stats?.notifiedToday || 0) / (stats?.totalProcessedToday || 1) * 100 | 0}%</p>
        </div>
        <div className="card p-5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">오늘 무시된 메일</p>
          <p className="mt-1 text-3xl font-bold text-gray-900">{stats?.silencedToday || 0}<span className="ml-1 text-sm font-normal text-gray-500">건</span></p>
          <p className="mt-1 text-xs text-gray-500">불필요한 메일 자동 분류</p>
        </div>
      </div>

      {/* ===== 이번 달 AI 비용 ===== */}
      {costStats && (
        <div className="card p-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* 좌: 월 누적 비용 + 지표 */}
            <div className="lg:col-span-5">
              <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                <Wallet className="h-4 w-4 text-blue-600" /> 이번 달 AI 비용
                <span className="text-xs font-normal text-gray-400">({costStats.period})</span>
              </h2>
              <p className="mt-3 text-3xl font-bold text-blue-700">₩{costStats.cost.totalKRW.toLocaleString()}</p>
              <p className="text-sm text-gray-500">${costStats.cost.totalUSD.toFixed(2)} USD</p>
              <p className="mt-1 text-xs text-amber-600 flex items-center gap-1"><AlertTriangle className="h-3 w-3 flex-shrink-0" /> {costStats.note}</p>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-gray-400">AI 호출</p>
                  <p className="text-lg font-semibold text-gray-900">{costStats.totalCalls.toLocaleString()}건</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">캐시 적중률</p>
                  <p className="text-lg font-semibold text-blue-600">{costStats.cacheHitRate}%</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">입력 토큰</p>
                  <p className="text-lg font-semibold text-gray-900">{(costStats.tokens.input / 1_000_000).toFixed(2)}M</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">출력 토큰</p>
                  <p className="text-lg font-semibold text-gray-900">{(costStats.tokens.output / 1_000_000).toFixed(2)}M</p>
                </div>
              </div>
            </div>

            {/* 우: 일별 추이 차트 */}
            <div className="lg:col-span-7">
              {costStats.dailyBreakdown.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-3">최근 일별 AI 호출 추이</h3>
                  <div className="flex items-end gap-1 h-32 bg-gray-50 rounded-lg p-2">
                    {costStats.dailyBreakdown.slice(-14).map((day, idx) => {
                      const maxCalls = Math.max(...costStats.dailyBreakdown.map(d => d.calls));
                      const heightPercent = maxCalls > 0 ? (day.calls / maxCalls) * 100 : 0;
                      return (
                        <div
                          key={idx}
                          className="flex-1 bg-blue-400 hover:bg-blue-600 rounded-t transition-colors cursor-pointer group relative"
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
          </div>
        </div>
      )}

      {/* ===== 빠른 작업 ===== */}
      <div className="card p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4">빠른 작업</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Link href="/users/new" className="flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-all group">
            <UserPlus className="h-7 w-7 mb-2 text-blue-600 group-hover:scale-110 transition-transform" />
            <span className="text-sm font-semibold">새 사용자 추가</span>
          </Link>
          <Link href="/events" className="flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-all group">
            <Search className="h-7 w-7 mb-2 text-blue-600 group-hover:scale-110 transition-transform" />
            <span className="text-sm font-semibold">메일 모니터링</span>
          </Link>
          <Link href="/audit" className="flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-all group">
            <ScrollText className="h-7 w-7 mb-2 text-blue-600 group-hover:scale-110 transition-transform" />
            <span className="text-sm font-semibold">변경 이력 확인</span>
          </Link>
          <Link href="/settings" className="flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-all group">
            <Settings className="h-7 w-7 mb-2 text-blue-600 group-hover:scale-110 transition-transform" />
            <span className="text-sm font-semibold">시스템 설정</span>
          </Link>
        </div>
      </div>

      {/* ===== 서비스 정보 ===== */}
      <div className="card p-6">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">서비스 정보</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2 text-sm">
          <div className="flex justify-between border-b border-gray-100 pb-2">
            <span className="text-gray-500">서비스 이름</span>
            <span className="text-gray-700 font-mono">Gmail Important Notifier</span>
          </div>
          <div className="flex justify-between border-b border-gray-100 pb-2">
            <span className="text-gray-500">버전</span>
            <span className="text-gray-700 font-mono">v1.2.0 (Next.js 14)</span>
          </div>
          <div className="flex justify-between border-b border-gray-100 pb-2">
            <span className="text-gray-500">스케줄 주기</span>
            <span className="text-gray-700 font-mono">5분 주기</span>
          </div>
          <div className="flex justify-between border-b border-gray-100 pb-2">
            <span className="text-gray-500">AI 엔진</span>
            <span className="text-gray-700 font-mono">AWS Bedrock (Claude Haiku 4.5)</span>
          </div>
        </div>
        <p className="mt-3 text-xs text-gray-400">* 데이터는 실시간으로 집계됩니다.</p>
      </div>
    </div>
  );
}
