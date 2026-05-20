/**
 * BASE_PATH 기반 URL 헬퍼
 * - 개발: BASE_URL = "/" → 빈 문자열
 * - 프로덕션: BASE_URL = "/embed/group-20/20_OrderAI/" → prefix 적용
 */
const BASE = import.meta.env.BASE_URL?.replace(/\/$/, '') || '';

/** public/ 정적 파일 URL (예: publicUrl('/season_closing_data.json')) */
export function publicUrl(path) {
  return `${BASE}${path}`;
}

/** API 엔드포인트 URL (예: apiUrl('/api/budget-proposal')) */
export function apiUrl(path) {
  return `${BASE}${path}`;
}
