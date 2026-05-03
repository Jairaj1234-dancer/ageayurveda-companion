import { useState, useCallback } from "react";
import { BrowserRouter, Routes, Route, NavLink, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Conversations from "./pages/Conversations";
import ConversationDetail from "./pages/ConversationDetail";
import Leads from "./pages/Leads";
import Analytics from "./pages/Analytics";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" },
  { to: "/conversations", label: "Conversations", icon: "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" },
  { to: "/leads", label: "Leads", icon: "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" },
  { to: "/analytics", label: "Analytics", icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" },
];

function Sidebar({ onLogout }: { onLogout: () => void }) {
  return (
    <aside className="w-56 bg-brand-brown text-white min-h-screen flex flex-col">
      <div className="p-4 border-b border-white/10">
        <h1 className="text-lg font-bold text-brand-amber">AgeAyurveda</h1>
        <p className="text-xs text-white/60">Admin Panel</p>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-white/15 text-brand-amber"
                  : "text-white/70 hover:bg-white/10 hover:text-white"
              }`
            }
          >
            <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
            </svg>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-3 border-t border-white/10">
        <button
          onClick={onLogout}
          className="w-full px-3 py-2 text-sm text-white/60 hover:text-white hover:bg-white/10 rounded-lg transition-colors text-left"
        >
          Logout
        </button>
      </div>
    </aside>
  );
}

export default function App() {
  const [token, setToken] = useState<string | null>(
    () => sessionStorage.getItem("admin_token")
  );

  const handleLogin = useCallback((t: string) => {
    sessionStorage.setItem("admin_token", t);
    setToken(t);
  }, []);

  const handleLogout = useCallback(() => {
    sessionStorage.removeItem("admin_token");
    setToken(null);
  }, []);

  if (!token) return <Login onLogin={handleLogin} />;

  return (
    <BrowserRouter basename="/admin">
      <div className="flex min-h-screen">
        <Sidebar onLogout={handleLogout} />
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard token={token} />} />
            <Route path="/conversations" element={<Conversations token={token} />} />
            <Route path="/conversations/:id" element={<ConversationDetail token={token} />} />
            <Route path="/leads" element={<Leads token={token} />} />
            <Route path="/analytics" element={<Analytics token={token} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
