/**
 * Lite 본인 변경 셀 강조 유틸 (4/29 결정)
 *
 * 정책: 본인 사물함 값 ≠ baseline 값일 때 셀 배경에 연한 노랑 적용.
 * 배지/툴팁 없음, 단순 색상만.
 */

// 매우 연한 노랑 + 40% 투명도. 너무 튀지 않게 부드럽게 강조.
export const CHANGED_CELL_CLASS = 'bg-yellow-100/40'

/** 두 값이 다른지 비교 (null/undefined/NaN 정규화 + 숫자 비교 시 epsilon) */
export function isChanged(userVal, baselineVal, epsilon = 0.5) {
  const a = userVal ?? null
  const b = baselineVal ?? null
  if (a === b) return false
  if (a == null || b == null) return true
  if (typeof a === 'number' && typeof b === 'number') {
    return Math.abs(a - b) > epsilon
  }
  return String(a) !== String(b)
}

/** className 합성 헬퍼 — 변경 시 노랑 배경 추가 */
export function highlightIfChanged(userVal, baselineVal, baseClass = '', epsilon = 0.5) {
  return isChanged(userVal, baselineVal, epsilon)
    ? `${baseClass} ${CHANGED_CELL_CLASS}`.trim()
    : baseClass
}
