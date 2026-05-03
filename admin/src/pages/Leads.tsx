import { useState, useEffect } from "react";
import { apiFetch } from "../api";

interface Lead {
  id: string;
  email: string;
  name: string | null;
  source: string | null;
  created_at: string;
}

export default function Leads({ token }: { token: string }) {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const perPage = 25;

  useEffect(() => {
    setLoading(true);
    apiFetch<{ leads: Lead[]; total: number }>(
      `/api/v1/admin/leads?page=${page}&per_page=${perPage}`,
      token
    )
      .then((data) => setLeads(data.leads || []))
      .catch(() => setLeads([]))
      .finally(() => setLoading(false));
  }, [token, page]);

  const downloadCSV = () => {
    if (leads.length === 0) return;
    const header = "Email,Name,Source,Captured At\n";
    const rows = leads
      .map((l) => `"${l.email}","${l.name || ""}","${l.source || ""}","${l.created_at}"`)
      .join("\n");
    const blob = new Blob([header + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `leads_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-800">Leads</h2>
        <button
          onClick={downloadCSV}
          disabled={leads.length === 0}
          className="px-4 py-2 text-sm bg-brand-green text-white rounded-lg hover:bg-green-800 disabled:opacity-30"
        >
          Export CSV
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Email</th>
              <th className="text-left px-4 py-3 font-medium">Name</th>
              <th className="text-left px-4 py-3 font-medium">Source</th>
              <th className="text-left px-4 py-3 font-medium">Captured</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
            ) : leads.length === 0 ? (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400">No leads yet</td></tr>
            ) : (
              leads.map((l) => (
                <tr key={l.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{l.email}</td>
                  <td className="px-4 py-3 text-gray-500">{l.name || "-"}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded-full text-xs bg-amber-100 text-amber-800">
                      {l.source || "widget"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{new Date(l.created_at).toLocaleString()}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between mt-4">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          className="px-3 py-1 text-sm border rounded disabled:opacity-30"
        >
          Previous
        </button>
        <span className="text-sm text-gray-500">Page {page}</span>
        <button
          onClick={() => setPage((p) => p + 1)}
          disabled={leads.length < perPage}
          className="px-3 py-1 text-sm border rounded disabled:opacity-30"
        >
          Next
        </button>
      </div>
    </div>
  );
}
