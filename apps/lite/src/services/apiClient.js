// Lite API 클라이언트 — /api/lite/* 호출에 X-User-Email 자동 부착
//
// 사용:
//   import { liteApi } from '../services/apiClient'
//   const data = await liteApi('/dashboard?brand=MLB&season=26f', { email: user.email })

// service/apiClient.js와 동일하게 Vite base path 사용 (Nginx 하위 경로 정합).
// VITE_API_BASE는 fallback (개발 환경에서 별도 backend host 지정 시).
const BASE = import.meta.env.VITE_API_BASE
  || (import.meta.env.BASE_URL?.replace(/\/$/, '') || '')

function _buildHeaders(email, roles, extra = {}) {
  const h = {
    'X-User-Email': email || '',
    ...extra,
  }
  if (Array.isArray(roles) && roles.length > 0) {
    h['X-User-Roles'] = roles.join(',')
  }
  return h
}

export async function liteApi(path, { email, roles, method = 'GET', body, headers, signal } = {}) {
  const init = {
    method,
    headers: _buildHeaders(email, roles, headers),
    signal,
  }
  if (body !== undefined && method !== 'GET') {
    init.headers['Content-Type'] = 'application/json'
    init.body = typeof body === 'string' ? body : JSON.stringify(body)
  }

  const url = `${BASE}/api/lite${path}`
  const resp = await fetch(url, init)

  // 204 No Content (order-recommendation 등) — 정상 분기
  if (resp.status === 204) return { status: 204, data: null }

  let data = null
  const ct = resp.headers.get('Content-Type') || ''
  if (ct.includes('application/json')) {
    data = await resp.json()
  } else {
    data = await resp.text()
  }

  if (!resp.ok) {
    const error = new Error(`Lite API ${path} 실패 (${resp.status})`)
    error.status = resp.status
    error.data = data
    throw error
  }
  return { status: resp.status, data }
}

// FormData (파일 업로드용 — go-list)
export async function liteApiUpload(path, { email, roles, formData, signal } = {}) {
  const url = `${BASE}/api/lite${path}`
  const resp = await fetch(url, {
    method: 'POST',
    headers: _buildHeaders(email, roles),
    body: formData,
    signal,
  })
  let data = null
  if ((resp.headers.get('Content-Type') || '').includes('application/json')) {
    data = await resp.json()
  }
  if (!resp.ok) {
    const error = new Error(`Lite upload ${path} 실패 (${resp.status})`)
    error.status = resp.status
    error.data = data
    throw error
  }
  return { status: resp.status, data }
}

// Excel 다운로드 (orders/excel) — Blob 반환
export async function liteApiDownloadBlob(path, { email, roles } = {}) {
  const url = `${BASE}/api/lite${path}`
  const resp = await fetch(url, { headers: _buildHeaders(email, roles) })
  if (!resp.ok) {
    const error = new Error(`Lite download ${path} 실패 (${resp.status})`)
    error.status = resp.status
    try {
      error.data = await resp.json()
    } catch {
      error.data = null
    }
    throw error
  }
  const blob = await resp.blob()
  const cd = resp.headers.get('Content-Disposition') || ''
  const match = cd.match(/filename="?([^"]+)"?/)
  const filename = match ? match[1] : 'download.xlsx'
  return { blob, filename }
}
