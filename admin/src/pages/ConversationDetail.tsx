import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { apiFetch } from "../api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: string | null;
  products: string | null;
  disclaimer: string | null;
  model_used: string | null;
  tokens_input: number | null;
  tokens_output: number | null;
  language: string;
  created_at: string;
}

interface ConversationData {
  id: string;
  title: string;
  language: string;
  message_count: number;
  created_at: string;
  messages: Message[];
}

export default function ConversationDetail({ token }: { token: string }) {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ConversationData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    apiFetch<ConversationData>(`/api/v1/admin/conversations/${id}`, token)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [id, token]);

  if (loading) return <div className="p-6 text-gray-400">Loading...</div>;
  if (!data) return <div className="p-6 text-red-500">Conversation not found</div>;

  return (
    <div className="p-6 max-w-4xl">
      <Link to="/conversations" className="text-sm text-brand-green hover:underline mb-4 inline-block">
        &larr; Back to Conversations
      </Link>

      <div className="mb-6">
        <h2 className="text-xl font-bold text-gray-800">{data.title || "Untitled"}</h2>
        <p className="text-sm text-gray-500">
          {data.message_count} messages &middot; {data.language?.toUpperCase()} &middot; Started {new Date(data.created_at).toLocaleString()}
        </p>
      </div>

      <div className="space-y-3">
        {data.messages.map((msg) => (
          <div
            key={msg.id}
            className={`p-4 rounded-xl max-w-[85%] ${
              msg.role === "user"
                ? "bg-brand-green text-white ml-auto"
                : "bg-white border border-gray-200"
            }`}
          >
            <div className="text-xs mb-1 opacity-60">
              {msg.role === "user" ? "User" : "Assistant"}
              {msg.model_used && msg.model_used !== "fallback" && ` (${msg.model_used})`}
              {" "}&middot; {new Date(msg.created_at).toLocaleTimeString()}
            </div>
            <div className="whitespace-pre-wrap text-sm">{msg.content}</div>
            {msg.citations && (
              <div className="mt-2 pt-2 border-t border-current/10 text-xs opacity-70">
                Citations: {msg.citations}
              </div>
            )}
            {msg.tokens_input != null && msg.tokens_input > 0 && (
              <div className="text-xs mt-1 opacity-50">
                Tokens: {msg.tokens_input} in / {msg.tokens_output} out
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
