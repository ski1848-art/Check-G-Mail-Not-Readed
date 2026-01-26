"use client";

import { useState, useEffect, useCallback } from "react";
import { format } from "date-fns";
import { ko } from "date-fns/locale";
import { Search, Mail, User, RefreshCw, Bell, BellOff, Calendar, Info } from "lucide-react";

interface EmailEvent {
  id: string;
  subject: string;
  from_email: string;
  to_email: string;
  final_category: string;
  llm_score_raw: number;
  reason: string; // 판별 사유 추가
  rule_decision: string;
  created_at: string;
  timestamp: string; // 실제 메일 수신 시각 추가
  slack_targets: string[];
  slack_targets_with_names?: { id: string; name: string }[];
}

export default function EventsPage() {
  const [events, setEvents] = useState<EmailEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [dateFilter, setDateFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [triggeringId, setTriggeringId] = useState<string | null>(null);
  const [blockingId, setBlockingId] = useState<string | null>(null);
  
  // 자동 새로고침 관련 상태 (기본 ON, 30초)
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [countdown, setCountdown] = useState(30);

  // fetchEvents를 useCallback으로 감싸서 polling에서 안전하게 호출 가능하게 함
  const fetchEvents = useCallback(async (isAuto = false) => {
    if (!isAuto) setLoading(true);
    try {
      let url = `/api/email-events?limit=100&t=${Date.now()}`;
      if (categoryFilter !== "all") {
        url += `&category=${categoryFilter}`;
      }
      if (dateFilter) {
        url += `&date=${dateFilter}`;
      }
      const res = await fetch(url, {
        cache: 'no-store',
        headers: {
          'Pragma': 'no-cache',
          'Cache-Control': 'no-cache'
        }
      });
      const data = await res.json();
      
      if (Array.isArray(data)) {
        setEvents(data);
      } else {
        console.error("API error or unexpected format:", data);
        setEvents([]); // 에러 발생 시 빈 배열로 초기화하여 크래시 방지
      }
    } catch (error) {
      console.error("Failed to fetch events:", error);
    } finally {
      if (!isAuto) setLoading(false);
    }
  }, [categoryFilter, dateFilter]);

  // 필터 변경 시 데이터 호출
  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // 자동 새로고침 타이머 (30초 주기)
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (autoRefresh) {
      timer = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            fetchEvents(true); // 30초 되면 자동 갱신
            return 30;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      setCountdown(30);
    }
    return () => clearInterval(timer);
  }, [autoRefresh, fetchEvents]);

  const handleManualTrigger = async (emailId: string) => {
    if (!confirm("이 메일에 대한 알림을 즉시 전송하고, 앞으로도 이 발신자의 메일은 알림을 보내도록 학습하시겠습니까?")) return;
    
    setTriggeringId(emailId);
    try {
      const res = await fetch(`/api/email-events/${emailId}/trigger`, {
        method: "POST"
      });
      const data = await res.json();
      
      if (res.ok) {
        alert("알림 전송 및 학습 요청이 완료되었습니다.");
        fetchEvents();
      } else {
        alert(`전송 실패: ${data.error || "알 수 없는 오류"}`);
      }
    } catch (error) {
      console.error("Manual trigger error:", error);
      alert("전송 중 네트워크 오류가 발생했습니다.");
    } finally {
      setTriggeringId(null);
    }
  };

  const handleManualBlock = async (emailId: string) => {
    if (!confirm("앞으로 이 발신자의 유사한 메일 알림을 모두 차단하시겠습니까? (AI가 학습합니다)")) return;
    
    setBlockingId(emailId);
    try {
      const res = await fetch(`/api/email-events/${emailId}/block`, {
        method: "POST"
      });
      const data = await res.json();
      
      if (res.ok) {
        alert("차단 및 학습 요청이 완료되었습니다.");
        fetchEvents();
      } else {
        alert(`요청 실패: ${data.error || "알 수 없는 오류"}`);
      }
    } catch (error) {
      console.error("Manual block error:", error);
      alert("요청 중 네트워크 오류가 발생했습니다.");
    } finally {
      setBlockingId(null);
    }
  };

  const filteredEvents = events.filter(event => 
    event.subject?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    event.from_email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    event.to_email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    event.slack_targets_with_names?.some(t => t.name.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">메일 처리 모니터링</h1>
          <p className="text-gray-500 text-sm mt-1">AI가 판별한 전체 메일 처리 이력을 실시간으로 확인합니다.</p>
        </div>
        <div className="flex items-center gap-4">
          {/* 자동 새로고침 표시 및 제어 */}
          <div className="flex items-center gap-3 px-4 py-2 bg-white rounded-xl border border-gray-200 shadow-sm">
            <div className={`flex items-center gap-2 ${autoRefresh ? 'text-blue-600' : 'text-gray-400'}`}>
              <div className={`h-2 w-2 rounded-full ${autoRefresh ? 'bg-blue-600 animate-pulse' : 'bg-gray-300'}`} />
              <span className="text-xs font-bold w-20">
                {autoRefresh ? `${countdown}초 후 갱신` : '자동 갱신 꺼짐'}
              </span>
            </div>
            <button 
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`text-[10px] px-2 py-1 rounded-lg font-black transition-all border ${
                autoRefresh 
                ? 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100' 
                : 'bg-gray-50 text-gray-500 border-gray-200 hover:bg-gray-100'
              }`}
            >
              {autoRefresh ? 'ON' : 'OFF'}
            </button>
          </div>

          <button 
            className={`btn ${loading ? 'bg-gray-100 text-gray-400' : 'btn-outline'} flex items-center gap-2`}
            onClick={() => fetchEvents()}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            {loading ? '갱신 중...' : '새로고침'}
          </button>
        </div>
      </div>

      <div className="card p-6 bg-white/50 backdrop-blur-sm shadow-sm rounded-xl border border-gray-200">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              placeholder="제목, 발신자, 대상자 성함 검색..."
              className="input pl-10 w-full"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-500">날짜:</span>
              <div className="relative">
                <Calendar className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-400 pointer-events-none" />
                <input
                  type="date"
                  value={dateFilter}
                  onChange={(e) => setDateFilter(e.target.value)}
                  className="input pl-8 py-1 h-10 w-[160px] text-sm"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-500">상태:</span>
              <select 
                value={categoryFilter} 
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="input w-[130px] py-1 h-10 text-sm"
              >
                <option value="all">전체</option>
                <option value="notify">✅ 알림 전송</option>
                <option value="silent">🔕 무시됨</option>
              </select>
            </div>
          </div>
        </div>

        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="table w-full border-collapse">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-left">
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-[180px]">수신 시각</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-[100px]">상태</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">메일 정보</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-[80px] text-center">사유</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-[120px] text-center">AI 점수</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-[150px]">대상자</th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-[120px] text-center">작업</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="h-32 text-center text-gray-500">
                    데이터를 불러오는 중...
                  </td>
                </tr>
              ) : filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan={7} className="h-32 text-center text-gray-500">
                    표시할 이력이 없습니다.
                  </td>
                </tr>
              ) : (
                filteredEvents.map((event) => (
                  <tr key={event.id} className="hover:bg-blue-50/30 transition-colors">
                    <td className="px-4 py-4 text-[13px] text-gray-500 font-medium">
                      {event.timestamp ? format(new Date(event.timestamp), "MM/dd HH:mm:ss", { locale: ko }) : "-"}
                    </td>
                    <td className="px-4 py-4">
                      {event.final_category === "notify" ? (
                        <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">알림 전송</span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-gray-50 px-2 py-1 text-xs font-medium text-gray-600 ring-1 ring-inset ring-gray-500/10">무시됨</span>
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex flex-col gap-1 max-w-md lg:max-w-xl">
                        <div className="font-semibold text-gray-900 line-clamp-1 text-sm">{event.subject || "(제목 없음)"}</div>
                        <div className="flex items-center gap-3 text-[11px] text-gray-500">
                          <span className="flex items-center gap-1">
                            <Mail className="h-3 w-3" /> {event.from_email}
                          </span>
                          <span className="text-gray-300">|</span>
                          <span className="flex items-center gap-1 font-medium text-blue-600">
                            <User className="h-3 w-3" /> {event.to_email}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <button
                        onClick={() => {
                          const displayReason = event.reason || 
                            (event.rule_decision?.toLowerCase() === 'rule' 
                              ? "시스템 규칙(Rule)에 의해 자동 분류된 메일입니다." 
                              : "AI 분석 결과 중요도가 낮아 별도의 상세 사유가 생성되지 않았습니다.");
                          alert(`📋 판별 사유\n\n${displayReason}`);
                        }}
                        className={`inline-flex items-center justify-center w-7 h-7 rounded-full transition-all border 
                          ${event.reason 
                            ? 'bg-blue-50 text-blue-600 border-blue-100 hover:bg-blue-100' 
                            : 'bg-gray-50 text-gray-400 border-gray-200 hover:bg-gray-100'}`}
                        title="판별 사유 보기"
                      >
                        <Info className="h-3.5 w-3.5" />
                      </button>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <div className="flex flex-col items-center gap-0.5">
                        <span className={`text-sm font-bold ${event.llm_score_raw >= 0.7 ? 'text-blue-600' : 'text-gray-400'}`}>
                          {event.llm_score_raw?.toFixed(2) || "0.00"}
                        </span>
                        <span className="text-[9px] text-gray-400 font-medium uppercase tracking-wider">
                          {event.rule_decision?.toUpperCase() === 'RULE' ? 'Rule' : 'AI'}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex flex-wrap gap-1">
                        {event.slack_targets_with_names?.length ? (
                          event.slack_targets_with_names.map(target => (
                            <span key={target.id} className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 border border-blue-100 font-medium">
                              {target.name}
                            </span>
                          ))
                        ) : event.slack_targets?.length > 0 ? (
                          event.slack_targets.map(target => (
                            <span key={target} className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 border border-blue-100 font-medium">
                              {target}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-gray-400">-</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-4 text-center">
                      {event.final_category === "silent" ? (
                        <button
                          onClick={() => handleManualTrigger(event.id)}
                          disabled={triggeringId === event.id}
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all
                            ${triggeringId === event.id 
                              ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                              : 'bg-blue-600 text-white hover:bg-blue-700 active:scale-95 shadow-sm hover:shadow'}`}
                        >
                          <Bell className={`h-3 w-3 ${triggeringId === event.id ? 'animate-pulse' : ''}`} />
                          {triggeringId === event.id ? '전송중' : '알림 전송'}
                        </button>
                      ) : (
                        <button
                          onClick={() => handleManualBlock(event.id)}
                          disabled={blockingId === event.id}
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all
                            ${blockingId === event.id 
                              ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                              : 'bg-gray-100 text-gray-600 hover:bg-red-50 hover:text-red-600 border border-gray-200 hover:border-red-200 active:scale-95'}`}
                        >
                          <BellOff className={`h-3 w-3 ${blockingId === event.id ? 'animate-pulse' : ''}`} />
                          {blockingId === event.id ? '처리중' : '앞으로 차단'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
