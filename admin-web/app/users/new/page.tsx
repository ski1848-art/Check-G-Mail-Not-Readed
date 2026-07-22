/**
 * users/new/page.tsx - 새 사용자 추가 페이지
 * 
 * [입력 필드]
 *   - Slack User ID (필수, U로 시작하는 대문자+숫자)
 *   - 표시 이름 (선택)
 *   - Gmail 계정 (복수 등록 가능, 이메일 형식 검증)
 *   - 알림 활성/비활성 토글
 * 
 * [저장] POST /api/routing-rules → Firestore routing_rules에 저장
 */
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useToast } from "@/components/ui/toast";
import { Mail, ArrowLeft } from "lucide-react";

export default function NewUserPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [formData, setFormData] = useState({
    slack_user_id: "",
    slack_display_name: "",
    gmail_accounts: [] as string[],
    enabled: true,
  });
  const [newGmail, setNewGmail] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleAddGmail = () => {
    if (!newGmail) return;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(newGmail)) {
      toast("올바른 이메일 형식이 아닙니다", "error");
      return;
    }
    if (formData.gmail_accounts.includes(newGmail.toLowerCase())) {
      toast("이미 등록된 이메일입니다", "error");
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
    if (!formData.slack_user_id || !/^U[A-Z0-9]+$/.test(formData.slack_user_id)) {
      toast("Slack User ID는 U로 시작하는 대문자와 숫자여야 합니다", "error");
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch("/api/routing-rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      if (res.ok) {
        router.push("/users");
      } else {
        const error = await res.json();
        toast(`저장 실패: ${error.error}`, "error");
      }
    } catch (err) {
      toast("오류가 발생했습니다", "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/users" className="text-gray-500 hover:text-blue-600" aria-label="목록으로">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">사용자 추가</h1>
          <p className="mt-1 text-sm text-gray-600">새로운 알림 수신자를 등록합니다</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="card p-6 space-y-6">
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">
            Slack 사용자 ID <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            placeholder="예: U04E9PMTLTZ"
            className="input font-mono uppercase"
            value={formData.slack_user_id}
            onChange={(e) => setFormData({ ...formData, slack_user_id: e.target.value.toUpperCase() })}
            required
          />
          <p className="text-xs text-gray-500">Slack 프로필 → 더보기 → 멤버 ID 복사</p>
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">이름</label>
          <input
            type="text"
            placeholder="예: 홍길동"
            className="input"
            value={formData.slack_display_name}
            onChange={(e) => setFormData({ ...formData, slack_display_name: e.target.value })}
          />
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
                  <Mail className="h-3.5 w-3.5" /> {email}
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
            {submitting ? "저장 중..." : "저장"}
          </button>
        </div>
      </form>
    </div>
  );
}
