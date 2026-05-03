import { useState, useEffect } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface DashboardProps {
  token: string;
}

interface Stats {
  total_conversations: number;
  total_messages: number;
  total_leads: number;
  total_prakriti_assessments: number;
  conversations_today: number;
  api_cost_today: number;
}

export default function Dashboard({ token }: DashboardProps) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/api/v1/admin/dashboard`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then(setStats)
      .catch(() => setError("Failed to load dashboard"));
  }, [token]);

  if (error) return <p className="text-red-500 p-4">{error}</p>;
  if (!stats) return <p className="p-4">Loading...</p>;

  const cards = [
    { label: "Total Conversations", value: stats.total_conversations, color: "bg-green-100 text-green-800" },
    { label: "Total Messages", value: stats.total_messages, color: "bg-blue-100 text-blue-800" },
    { label: "Total Leads", value: stats.total_leads, color: "bg-amber-100 text-amber-800" },
    { label: "Prakriti Assessments", value: stats.total_prakriti_assessments, color: "bg-purple-100 text-purple-800" },
    { label: "Conversations Today", value: stats.conversations_today, color: "bg-teal-100 text-teal-800" },
    { label: "API Cost Today ($)", value: stats.api_cost_today.toFixed(4), color: "bg-red-100 text-red-800" },
  ];

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold mb-6">Dashboard</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {cards.map((card) => (
          <div key={card.label} className={`p-6 rounded-xl ${card.color}`}>
            <div className="text-sm font-medium opacity-80">{card.label}</div>
            <div className="text-3xl font-bold mt-1">{card.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
