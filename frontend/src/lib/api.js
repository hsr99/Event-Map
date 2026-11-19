// Base URL of the FastAPI backend (poster extraction + submissions).
// Set VITE_API_URL in the repo-root .env; defaults to the local dev server.
export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

// Pull a readable message out of a FastAPI error response.
export async function errorMessage(res) {
  try {
    const body = await res.json();
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((d) => d.msg).join('; ');
  } catch {
    /* not JSON */
  }
  return `Request failed (${res.status})`;
}

// Calls to the admin review desk. Throws an Error carrying the HTTP status on failure.
export async function adminRequest(token, path, { method = 'GET', body } = {}) {
  const headers = { Authorization: `Bearer ${token}` };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const err = new Error(await errorMessage(res));
    err.status = res.status;
    throw err;
  }
  return res.json();
}
