const STORAGE_PREFIX = "ageayurveda_";

export function getSessionId(): string {
  const key = `${STORAGE_PREFIX}session_id`;
  let sessionId = localStorage.getItem(key);
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    localStorage.setItem(key, sessionId);
  }
  return sessionId;
}

export function getEmail(): string | null {
  return localStorage.getItem(`${STORAGE_PREFIX}email`);
}

export function setEmail(email: string): void {
  localStorage.setItem(`${STORAGE_PREFIX}email`, email);
}

export function getMessageCount(): number {
  return parseInt(localStorage.getItem(`${STORAGE_PREFIX}msg_count`) || "0", 10);
}

export function incrementMessageCount(): number {
  const count = getMessageCount() + 1;
  localStorage.setItem(`${STORAGE_PREFIX}msg_count`, count.toString());
  return count;
}

export function getConversationId(): string | null {
  return localStorage.getItem(`${STORAGE_PREFIX}conversation_id`);
}

export function setConversationId(id: string | null): void {
  if (id === null) {
    localStorage.removeItem(`${STORAGE_PREFIX}conversation_id`);
  } else {
    localStorage.setItem(`${STORAGE_PREFIX}conversation_id`, id);
  }
}

export function getLanguage(): string {
  return localStorage.getItem(`${STORAGE_PREFIX}language`) || "auto";
}

export function setLanguage(lang: string): void {
  localStorage.setItem(`${STORAGE_PREFIX}language`, lang);
}
