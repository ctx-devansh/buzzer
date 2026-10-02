import { getToken } from './auth';

const BASE = '/api';

/** Error message from a non-2xx response: FastAPI's `detail`, or a BuzzerError's `message`. */
async function errorMessage(res: Response): Promise<string> {
  const err = (await res.json().catch(() => ({}))) as { detail?: unknown; message?: unknown };
  if (typeof err.detail === 'string') return err.detail;
  if (typeof err.message === 'string') return err.message;
  return `HTTP ${res.status}`;
}

async function apiFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers as Record<string, string> ?? {}),
    },
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  const text = await res.text();
  return text ? (JSON.parse(text) as T) : ({} as T);
}

/**
 * Trigger a file download. Bypasses apiFetch on purpose: it needs the raw response
 * for Content-Disposition and the blob.
 */
async function downloadFetch(path: string): Promise<void> {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  const disposition = res.headers.get('Content-Disposition') ?? '';
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : 'download';
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'PUT', body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: 'PATCH', body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: 'DELETE' }),
  /**
   * POST multipart/form-data (file uploads). Bypasses apiFetch on purpose: apiFetch
   * always sets Content-Type: application/json, which would break the multipart boundary.
   */
  postForm: <T>(path: string, form: FormData) => {
    const token = getToken();
    return fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    }).then(async (res) => {
      if (!res.ok) throw new Error(await errorMessage(res));
      const text = await res.text();
      return (text ? JSON.parse(text) : {}) as T;
    });
  },
  download: downloadFetch,
};
