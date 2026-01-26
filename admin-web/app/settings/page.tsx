"use client";

import { useState, useEffect } from "react";
import { Slider } from "@/components/ui/slider";
import { 
  Save, 
  RotateCcw, 
  Plus, 
  X, 
  ShieldCheck, 
  AlertTriangle, 
  BrainCircuit, 
  Clock
} from "lucide-react";

interface Settings {
  score_threshold_notify: number;
  routing_cache_ttl: number;
  blacklist_domains: string[];
  whitelist_domains: string[];
  spam_keywords: string[];
  urgent_keywords: string[];
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState("ai");

  // Temporary inputs for chips
  const [newBlacklist, setNewBlacklist] = useState("");
  const [newWhitelist, setNewWhitelist] = useState("");
  const [newSpam, setNewSpam] = useState("");
  const [newUrgent, setNewUrgent] = useState("");

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const res = await fetch("/api/settings");
      const data = await res.json();
      setSettings(data);
    } catch (error) {
      console.error("Failed to fetch settings:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (res.ok) {
        alert("시스템 설정이 성공적으로 업데이트되었습니다.");
      } else {
        throw new Error("Failed to save");
      }
    } catch (error) {
      alert("설정을 저장하는 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const addChip = (field: keyof Settings, value: string, setter: (v: string) => void) => {
    if (!settings || !value.trim()) return;
    const current = settings[field] as string[];
    if (current.includes(value.trim())) return;
    
    setSettings({
      ...settings,
      [field]: [...current, value.trim()]
    });
    setter("");
  };

  const removeChip = (field: keyof Settings, value: string) => {
    if (!settings) return;
    setSettings({
      ...settings,
      [field]: (settings[field] as string[]).filter(v => v !== value)
    });
  };

  if (loading || !settings) return <div className="p-8 text-center">설정을 불러오는 중...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-20">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">시스템 설정</h1>
          <p className="text-gray-500 text-sm mt-1">AI 판별 로직 및 필터링 정책을 전역적으로 관리합니다.</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-secondary" onClick={fetchSettings} disabled={saving}>
            <RotateCcw className="mr-2 h-4 w-4" /> 리셋
          </button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? "저장 중..." : <><Save className="mr-2 h-4 w-4" /> 모든 설정 저장</>}
          </button>
        </div>
      </div>

      <div className="flex border-b border-gray-200 mb-6">
        <button 
          className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${activeTab === 'ai' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          onClick={() => setActiveTab('ai')}
        >
          AI & 성능
        </button>
        <button 
          className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${activeTab === 'keywords' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          onClick={() => setActiveTab('keywords')}
        >
          키워드 필터
        </button>
        <button 
          className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${activeTab === 'domains' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          onClick={() => setActiveTab('domains')}
        >
          도메인 정책
        </button>
      </div>

      {activeTab === 'ai' && (
        <div className="space-y-6">
          <div className="card p-6">
            <h3 className="text-lg font-bold flex items-center gap-2 mb-2">
              <BrainCircuit className="h-5 w-5 text-blue-600" /> AI 판별 민감도
            </h3>
            <p className="text-sm text-gray-500 mb-6">AI가 분석한 중요도 점수가 이 값 이상일 때만 알림을 보냅니다.</p>
            
            <div className="space-y-6 px-2">
              <div className="flex justify-between items-center">
                <span className="text-sm font-semibold text-gray-700">알림 임계값 (Notification Threshold)</span>
                <span className="text-3xl font-bold text-blue-600">{settings.score_threshold_notify.toFixed(2)}</span>
              </div>
              <Slider 
                value={[settings.score_threshold_notify]} 
                min={0.1} 
                max={0.9} 
                step={0.05}
                onValueChange={(v) => setSettings({...settings, score_threshold_notify: v[0]})}
                className="py-4"
              />
              <div className="flex justify-between text-[11px] text-gray-400 font-medium uppercase tracking-wider">
                <span>민감하게 (알림 많아짐)</span>
                <span>보수적으로 (알림 적어짐)</span>
              </div>
            </div>
          </div>

          <div className="card p-6">
            <h3 className="text-lg font-bold flex items-center gap-2 mb-2">
              <Clock className="h-5 w-5 text-blue-600" /> 시스템 성능
            </h3>
            <div className="mt-4 flex items-center gap-6">
              <div className="flex-1">
                <label className="text-sm font-medium text-gray-700 block mb-1">라우팅 캐시 TTL (초)</label>
                <input 
                  type="number" 
                  value={settings.routing_cache_ttl}
                  onChange={(e) => setSettings({...settings, routing_cache_ttl: parseInt(e.target.value)})}
                  className="input max-w-[120px]"
                />
              </div>
              <p className="flex-[2] text-xs text-gray-500 bg-blue-50 p-3 rounded-lg border border-blue-100">
                Firestore 재조회 주기입니다. 값이 클수록 API 호출 비용이 절감되나, 관리자 웹에서의 변경사항이 알림 서비스에 반영되기까지 시간이 더 걸립니다.
              </p>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'keywords' && (
        <div className="space-y-6">
          <div className="card p-6 border-t-4 border-t-green-500">
            <h3 className="text-lg font-bold flex items-center gap-2 text-green-700 mb-1">
              <ShieldCheck className="h-5 w-5" /> 무조건 알림 키워드 (Urgent)
            </h3>
            <p className="text-sm text-gray-500 mb-4">제목에 이 키워드가 포함되면 AI 분석 없이 즉시 알림을 보냅니다.</p>
            <div className="flex gap-2 mb-4">
              <input 
                placeholder="새 키워드 추가..." 
                className="input flex-1"
                value={newUrgent} 
                onChange={(e) => setNewUrgent(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addChip('urgent_keywords', newUrgent, setNewUrgent)}
              />
              <button className="btn btn-primary px-3" onClick={() => addChip('urgent_keywords', newUrgent, setNewUrgent)}>
                <Plus className="h-4 w-4" />
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {settings.urgent_keywords.map(kw => (
                <span key={kw} className="badge bg-green-50 text-green-700 border border-green-200">
                  {kw} <X className="ml-1.5 h-3 w-3 cursor-pointer hover:text-red-500" onClick={() => removeChip('urgent_keywords', kw)} />
                </span>
              ))}
            </div>
          </div>

          <div className="card p-6 border-t-4 border-t-red-500">
            <h3 className="text-lg font-bold flex items-center gap-2 text-red-700 mb-1">
              <AlertTriangle className="h-5 w-5" /> 무조건 차단 키워드 (Spam)
            </h3>
            <p className="text-sm text-gray-500 mb-4">제목에 이 키워드가 포함되면 즉시 필터링합니다.</p>
            <div className="flex gap-2 mb-4">
              <input 
                placeholder="새 스팸 키워드 추가..." 
                className="input flex-1"
                value={newSpam} 
                onChange={(e) => setNewSpam(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addChip('spam_keywords', newSpam, setNewSpam)}
              />
              <button className="btn btn-danger px-3 text-white" onClick={() => addChip('spam_keywords', newSpam, setNewSpam)}>
                <Plus className="h-4 w-4" />
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {settings.spam_keywords.map(kw => (
                <span key={kw} className="badge bg-red-50 text-red-700 border border-red-200">
                  {kw} <X className="ml-1.5 h-3 w-3 cursor-pointer hover:text-red-500" onClick={() => removeChip('spam_keywords', kw)} />
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'domains' && (
        <div className="space-y-6">
          <div className="card p-6">
            <h3 className="text-lg font-bold mb-1">화이트리스트 도메인</h3>
            <p className="text-sm text-gray-500 mb-4">이 도메인에서 오는 모든 메일은 중요하게 취급됩니다.</p>
            <div className="flex gap-2 mb-4">
              <input 
                placeholder="example.com" 
                className="input flex-1"
                value={newWhitelist} 
                onChange={(e) => setNewWhitelist(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addChip('whitelist_domains', newWhitelist, setNewWhitelist)}
              />
              <button className="btn btn-primary px-3" onClick={() => addChip('whitelist_domains', newWhitelist, setNewWhitelist)}>
                <Plus className="h-4 w-4" />
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {settings.whitelist_domains.map(dom => (
                <span key={dom} className="badge badge-gray border border-gray-200">
                  {dom} <X className="ml-1.5 h-3 w-3 cursor-pointer hover:text-red-500" onClick={() => removeChip('whitelist_domains', dom)} />
                </span>
              ))}
            </div>
          </div>

          <div className="card p-6">
            <h3 className="text-lg font-bold mb-1">블랙리스트 도메인</h3>
            <p className="text-sm text-gray-500 mb-4">이 도메인에서 오는 메일은 AI 분석을 거치지 않고 차단합니다.</p>
            <div className="flex gap-2 mb-4">
              <input 
                placeholder="marketing.com" 
                className="input flex-1"
                value={newBlacklist} 
                onChange={(e) => setNewBlacklist(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addChip('blacklist_domains', newBlacklist, setNewBlacklist)}
              />
              <button className="btn btn-primary px-3" onClick={() => addChip('blacklist_domains', newBlacklist, setNewBlacklist)}>
                <Plus className="h-4 w-4" />
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {settings.blacklist_domains.map(dom => (
                <span key={dom} className="badge badge-gray border border-gray-200">
                  {dom} <X className="ml-1.5 h-3 w-3 cursor-pointer hover:text-red-500" onClick={() => removeChip('blacklist_domains', dom)} />
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

