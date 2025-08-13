// /core/static/core/js/http.js
// Minimal helper to ensure cookies + CSRF header on non-GET requests.

export function getCookie(name) {
  // Robust cookie reader
  const parts = document.cookie ? document.cookie.split('; ') : [];
  for (let i = 0; i < parts.length; i++) {
    const [k, ...rest] = parts[i].split('=');
    if (k === name) return decodeURIComponent(rest.join('='));
  }
  // Fallback: try meta tag if cookie is HttpOnly or unavailable
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : null;
}

export async function api(url, { method = 'GET', headers = {}, body } = {}) {
  const opts = {
    method,
    credentials: 'same-origin',              // send cookies
    headers: { 'X-Requested-With': 'XMLHttpRequest', ...headers },
  };

  // Attach CSRF on mutable requests
  if (method !== 'GET' && method !== 'HEAD') {
    const token = getCookie('csrftoken');
    if (token) opts.headers['X-CSRFToken'] = token;
    if (body && !(body instanceof FormData)) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    } else {
      opts.body = body ?? null;
    }
  } else {
    // For GET/HEAD we still allow JSON convenience
    if (body && !(body instanceof FormData)) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    } else if (body) {
      opts.body = body;
    }
  }

  const res = await fetch(url, opts);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status} on ${url} :: ${text.slice(0, 300)}`);
  }
  const ct = res.headers.get('Content-Type') || '';
  return ct.includes('application/json') ? res.json() : res.text();
}
