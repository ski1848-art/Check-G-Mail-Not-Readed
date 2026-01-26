"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";

interface Preference {
  id: string;
  sender: string;
  created_at: string;
}

interface NotificationHistory {
  id: string;
  subject: string;
  from_email: string;
  final_category: string;
  created_at: string;
}

export default function EditUserPage() {
  const router = useRouter();
  const params = useParams();
  const slackUserId = params.slackUserId as string;

  const [formData, setFormData] = useState({
    slack_user_id: "",
    slack_display_name: "",
    gmail_accounts: [] as string[],
    enabled: true,
  });
  const [newGmail, setNewGmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  
  // New States
  const [preferences, setPreferences] = useState<Preference[]>([]);
  const [history, setHistory] = useState<NotificationHistory[]>([]);
  const [loadingExtras, setLoadingExtras] = useState(true);

  useEffect(() => {
    // Basic user info
    fetch(`/api/routing-rules/${slackUserId}`)
      .then(res => res.json())
      .then(data => {
        setFormData({
          slack_user_id: data.slack_user_id,
          slack_display_name: data.slack_display_name || "",
          gmail_accounts: data.gmail_accounts || [],
          enabled: data.enabled ?? true,
        });
        setLoading(false);
      });

    // Load Extras (Preferences and History)
    loadExtras();
  }, [slackUserId]);

  const loadExtras = async () => {
    setLoadingExtras(true);
    try {
      const [prefsRes, histRes] = await Promise.all([
        fetch(`/api/routing-rules/${slackUserId}/preferences`),
        fetch(`/api/routing-rules/${slackUserId}/history`)
      ]);
      
      if (prefsRes.ok) setPreferences(await prefsRes.json());
      if (histRes.ok) setHistory(await histRes.json());
    } catch (err) {
      console.error("Failed to load extra data:", err);
    } finally {
      setLoadingExtras(false);
    }
  };

  const handleAddGmail = () => {
    if (!newGmail) return;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(newGmail)) {
      alert("올바른 이메일 형식이 아닙니다");
      return;
    }
    if (formData.gmail_accounts.includes(newGmail.toLowerCase())) {
      alert("이미 등록된 이메일입니다");
      return;
    }
    setFormData({
      ...formData,
      gmail_accounts: [...formData.gmail_accounts, newGmail.toLowerCase().trim()],
    });
    setNewGmail("");
  };

  const removeGmail = (email: string) => {
    setFormData({
      ...formData,
      gmail_accounts: formData.gmail_accounts.filter(e => e !== email),
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await fetch(`/api/routing-rules/${slackUserId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      if (res.ok) {
        router.push("/users");
      } else {
        const error = await res.json();
        alert(`저장 실패: ${error.error}`);
      }
    } catch (err) {
      alert("오류가 발생했습니다");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    try {
      const res = await fetch(`/api/routing-rules/${slackUserId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        router.push("/users");
      } else {
        alert("삭제 실패");
      }
    } catch (err) {
      alert("오류 발생");
    }
  };

  const unblockSender = async (sender: string) => {
    if (!confirm(`${sender} 발신자의 알림 차단을 해제하시겠습니까?`)) return;
    
    try {
      const res = await fetch(`/api/routing-rules/${slackUserId}/preferences?sender=${encodeURIComponent(sender)}`, {
        method: "DELETE"
      });
      if (res.ok) {
        setPreferences(preferences.filter(p => p.sender !== sender));
      } else {
        alert("해제 실패");
      }
    } catch (err) {
      alert("오류 발생");
    }
  };

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

  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-12">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/users" className="text-2xl hover:text-blue-600">
            ←
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">사용자 설정 및 이력</h1>
            <p className="mt-1 text-sm text-gray-600">{formData.slack_user_id} · {formData.slack_display_name}</p>
          </div>
        </div>
        <button
          onClick={() => setShowDeleteConfirm(true)}
          className="text-sm text-gray-500 hover:text-red-600 font-medium"
        >
          사용자 삭제
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Profile & Accounts */}
        <div className="lg:col-span-2 space-y-6">
          <form onSubmit={handleSubmit} className="card p-6 space-y-6">
            <h2 className="text-lg font-semibold border-b pb-2">기본 정보</h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700">Slack 사용자 ID</label>
                <input
                  type="text"
                  className="input bg-gray-50 font-mono cursor-not-allowed"
                  value={formData.slack_user_id}
                  disabled
                />
              </div>

              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700">표시 이름</label>
                <input
                  type="text"
                  placeholder="예: 홍길동"
                  className="input"
                  value={formData.slack_display_name}
                  onChange={(e) => setFormData({ ...formData, slack_display_name: e.target.value })}
                />
              </div>
            </div>

            <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50 p-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">알림 상태</label>
                <p className="text-xs text-gray-500">이 사용자에게 알림을 전송합니다</p>
              </div>
              <label className="relative inline-flex cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.enabled}
                  onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="h-6 w-11 rounded-full bg-gray-300 peer-checked:bg-blue-600 transition-colors after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-all peer-checked:after:translate-x-5 after:shadow-md" />
              </label>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">Gmail 계정</label>
              <div className="flex gap-2">
                <input
                  type="email"
                  placeholder="이메일 주소를 입력하세요"
                  className="input flex-1"
                  value={newGmail}
                  onChange={(e) => setNewGmail(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleAddGmail())}
                />
                <button type="button" onClick={handleAddGmail} className="btn btn-outline">
                  추가
                </button>
              </div>
              {formData.gmail_accounts.length > 0 && (
                <div className="flex flex-wrap gap-2 pt-2">
                  {formData.gmail_accounts.map((email) => (
                    <span key={email} className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm text-blue-700">
                      📧 {email}
                      <button
                        type="button"
                        onClick={() => removeGmail(email)}
                        className="text-blue-600 hover:text-blue-800 text-lg leading-none"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
              <Link href="/users" className="btn btn-secondary">
                취소
              </Link>
              <button type="submit" disabled={submitting} className="btn btn-primary">
                {submitting ? "저장 중..." : "설정 저장"}
              </button>
            </div>
          </form>

          {/* History Section */}
          <div className="card p-6 space-y-6">
            <div className="flex items-center justify-between border-b pb-2">
              <h2 className="text-lg font-semibold">최근 알림 이력</h2>
              <span className="text-xs text-gray-500">최근 50개</span>
            </div>
            
            {loadingExtras ? (
              <p className="text-sm text-center py-4 text-gray-500">이력 불러오는 중...</p>
            ) : history.length === 0 ? (
              <p className="text-sm text-center py-8 text-gray-400">최근 알림 이력이 없습니다.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-gray-500 uppercase bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 font-medium">시간</th>
                      <th className="px-4 py-2 font-medium">발신자 / 제목</th>
                      <th className="px-4 py-2 font-medium">결과</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {history.map((item) => (
                      <tr key={item.id} className="hover:bg-gray-50/50">
                        <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                          {new Date(item.created_at).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td className="px-4 py-3">
                          <p className="font-medium text-gray-900 truncate max-w-xs">{item.from_email}</p>
                          <p className="text-xs text-gray-500 truncate max-w-xs">{item.subject}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                            item.final_category === 'notify' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                          }`}>
                            {item.final_category === 'notify' ? '알림' : '무시'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Preferences/Blocklist */}
        <div className="space-y-6">
          <div className="card p-6 space-y-6 bg-amber-50/30 border-amber-100">
            <div className="flex items-center gap-2 border-b border-amber-200 pb-2">
              <span className="text-xl">🔕</span>
              <h2 className="text-lg font-semibold text-amber-900">사용자 차단 목록</h2>
            </div>
            <p className="text-xs text-amber-700">
              사용자가 Slack에서 직접 "알림 끄기"를 선택한 발신자들입니다. 여기서 해제하면 다시 알림이 전송됩니다.
            </p>
            
            {loadingExtras ? (
              <p className="text-sm text-center py-4 text-amber-600/60">불러오는 중...</p>
            ) : preferences.length === 0 ? (
              <div className="text-center py-8 text-amber-600/40">
                <p className="text-sm">차단된 발신자가 없습니다.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {preferences.map((pref) => (
                  <div key={pref.id} className="flex items-center justify-between p-3 rounded-lg bg-white border border-amber-200 shadow-sm">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{pref.sender}</p>
                      <p className="text-[10px] text-gray-400">차단일: {new Date(pref.created_at).toLocaleDateString()}</p>
                    </div>
                    <button
                      onClick={() => unblockSender(pref.sender)}
                      className="text-xs font-semibold text-blue-600 hover:text-blue-800 px-2 py-1"
                    >
                      해제
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card p-6 space-y-4 bg-blue-50/30 border-blue-100">
            <h2 className="text-sm font-semibold text-blue-900 uppercase tracking-wider">도움말</h2>
            <ul className="text-xs text-blue-800 space-y-2 list-disc pl-4">
              <li>사용자가 알림을 못 받는다면 먼저 <b>차단 목록</b>을 확인하세요.</li>
              <li><b>알림 이력</b>에서 AI가 왜 '무시'했는지 판단 근거를 확인할 수 있습니다.</li>
              <li>사용자가 차단을 해제해도 <b>AI 학습</b> 결과에 따라 여전히 알림이 가지 않을 수 있습니다.</li>
            </ul>
          </div>
        </div>
      </div>

      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="card p-6 max-w-sm w-full mx-4 shadow-xl">
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100 text-2xl">
                ⚠️
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">사용자 삭제</h3>
                <p className="text-sm text-gray-600 mb-6">
                  정말 이 사용자를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.
                </p>
                <div className="flex justify-end gap-3">
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    className="btn btn-secondary"
                  >
                    취소
                  </button>
                  <button
                    onClick={handleDelete}
                    className="btn btn-danger"
                  >
                    삭제
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
