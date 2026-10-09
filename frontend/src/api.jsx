export const API_URL = "http://localhost:8000";

// An anonymous ID saved in this browser, so "my history" only shows my interviews
export function getClientId() {
  try {
    let id = localStorage.getItem("vic_client_id");
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem("vic_client_id", id);
    }
    return id;
  } catch {
    return crypto.randomUUID();
  }
}