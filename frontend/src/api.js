export function role() {
  return localStorage.getItem("hr-role") || "hr";
}

export function setRole(value) {
  localStorage.setItem("hr-role", value);
}

export async function api(path, options = {}) {
  const headers = { "X-Role": role(), ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, { ...options, headers });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === "string" ? detail : response.statusText;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}
