const API_BASE_URL = 'http://localhost:8000/api';

async function request(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;

  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  const response = await fetch(url, {
    headers: {
      ...defaultHeaders,
      ...(options.headers || {}),
    },
    ...options,
  });

  const isJson = response.headers
    .get('content-type')
    ?.includes('application/json');

  const data = isJson ? await response.json() : null;

  if (!response.ok) {
    // 에러 형식은 명세 참고 
    const error = new Error(data?.error || 'API 요청 실패');
    error.status = response.status;
    error.detail = data?.detail;
    throw error;
  }

  return data;
}

export function get(path, params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
  ).toString();

  const fullPath = query ? `${path}?${query}` : path;
  return request(fullPath, { method: 'GET' });
}

export function post(path, body = {}) {
  return request(path, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}


export function patch(path, body = {}) {
  return request(path, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}
