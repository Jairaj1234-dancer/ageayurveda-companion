import { useState, useEffect } from "react";
import { apiFetch } from "../api";

interface Stats {
  total_conversations: number;
  total_messages: number;
  total_leads: number;
  total_prakriti_assessments: number;
  conversations_today: number;
  api_cost_today: number;
}

function Bar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-gray-600 w-32 text-right">{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-mono w-16 text-right">{value.toLocaleString()}</span>
    </div>
  );
}

export default function Analytics({ token }: { token: string }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<Stats>("/api/v1/admin/dashboard", token)
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <div className="p-6 text-gray-400">Loading analytics...</div>;
  if (!stats) return <div className="p-6 text-red-500">Failed to load analytics</div>;

  const maxMetric = Math.max(
    stats.total_conversations,
    stats.total_messages,
    stats.total_leads,
    stats.total_prakriti_assessments,
    1
  );

  const costPerConvo =
    stats.total_conversations > 0
      ? (stats.api_cost_today / Math.max(stats.conversations_today, 1)).toFixed(4)
      : "0.0000";

  return (
    <div className="p-6 max-w-4xl">
      <h2 className="text-xl font-bold text-gray-800 mb-6">Analytics</h2>

      <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase mb-4">Overall Metrics</h3>
        <div className="space-y-3">
          <Bar label="Conversations" value={stats.total_conversations} max={maxMetric} color="bg-brand-green" />
          <Bar label="Messages" value={stats.total_messages} max={maxMetric} color="bg-blue-500" />
          <Bar label="Leads" value={stats.total_leads} max={maxMetric} color="bg-brand-amber" />
          <Bar label="Prakriti Quizzes" value={stats.total_prakriti_assessments} max={maxMetric} color="bg-purple-500" />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="text-sm text-gray-500">Conversations Today</div>
          <div className="text-3xl font-bold text-brand-green mt-1">{stats.conversations_today}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="text-sm text-gray-500">API Cost Today</div>
          <div className="text-3xl font-bold text-red-600 mt-1">${stats.api_cost_today.toFixed(4)}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="text-sm text-gray-500">Cost per Conversation</div>
          <div className="text-3xl font-bold text-amber-600 mt-1">${costPerConvo}</div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase mb-4">Conversion Funnel</h3>
        <div className="space-y-2">
          <FunnelRow label="Conversations Started" value={stats.total_conversations} pct={100} />
          <FunnelRow
            label="Leads Captured"
            value={stats.total_leads}
            pct={stats.total_conversations > 0 ? (stats.total_leads / stats.total_conversations) * 100 : 0}
          />
          <FunnelRow
            label="Prakriti Completed"
            value={stats.total_prakriti_assessments}
            pct={stats.total_conversations > 0 ? (stats.total_prakriti_assessments / stats.total_conversations) * 100 : 0}
          />
        </div>
      </div>
    </div>
  );
}

function FunnelRow({ label, value, pct }: { label: string; value: number; pct: number }) {
  return (
    <div className="flex items-center gap-4">
      <div className="flex-1">
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm text-gray-700">{label}</span>
          <span className="text-sm font-medium">{value.toLocaleString()} ({pct.toFixed(1)}%)</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2.5">
          <div className="bg-brand-green h-2.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  );
}
