import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../api";

interface Conversation {
  id: string;
  title: string;
  language: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  user_email: string | null;
}

export default function Conversations({ token }: { token: string }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const perPage = 20;

  useEffect(() => {
    setLoading(true);
    apiFetch<{ conversations: Conversation[]; total: number }>(
      `/api/v1/admin/conversations?page=${page}&per_page=${perPage}&search=${encodeURIComponent(search)}`,
      token
    )
      .then((data) => {
        setConversations(data.conversations || []);
      })
      .catch(() => setConversations([]))
      .finally(() => setLoading(false));
  }, [token, page, search]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-800">Conversations</h2>
        <input
          type="search"
          placeholder="Search conversations..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="px-4 py-2 border rounded-lg w-72 text-sm"
        />
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Title</th>
              <th className="text-left px-4 py-3 font-medium">User</th>
              <th className="text-center px-4 py-3 font-medium">Messages</th>
              <th className="text-center px-4 py-3 font-medium">Lang</th>
              <th className="text-left px-4 py-3 font-medium">Last Active</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
            ) : conversations.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">No conversations found</td></tr>
            ) : (
              conversations.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <Link to={`/conversations/${c.id}`} className="text-brand-green hover:underline font-medium">
                      {c.title || "Untitled"}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{c.user_email || "Anonymous"}</td>
                  <td className="px-4 py-3 text-center">{c.message_count}</td>
                  <td className="px-4 py-3 text-center">
                    <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100">{c.language?.toUpperCase()}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{new Date(c.updated_at).toLocaleString()}</td>
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
          disabled={conversations.length < perPage}
          className="px-3 py-1 text-sm border rounded disabled:opacity-30"
        >
          Next
        </button>
      </div>
    </div>
  );
}
