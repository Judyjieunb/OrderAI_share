/**
 * Step 5 사이즈 분배 통합 알고리즘
 *
 * 참조: docs/STEP5_사이즈배분_운영가이드.md
 *   §8.2 사이즈 매칭 통합 폴백 체인 (L1~L5)
 *   §8.3 폴백 트리거 (SC ≥ 10, FIT Null → L1 스킵)
 *   §5 Step 1 인접 분배 → Step 2 빈자리 채우기 → Step 3 정규화
 */

const SC_THRESHOLD = 10;
const POLICY3_ALPHA = 0.5; // 정책 3 인접 비례 폴백 가중치

// L1 → L5 폴백 체인. keys는 matchInput에서 가져올 필드명.
const LEVEL_CONFIG = [
  { key: 'L1', countKey: 'by_l1', distKey: 'by_l1',
    keys: ['sex', 'class2', 'item', 'sesn', 'fit'],
    fields: ['SEX_NM', 'CLASS2', 'ITEM', 'SESN_SUB_NM', 'FIT_INFO1'],
    label: 'SEX × CLASS × ITEM × SESN × FIT' },
  { key: 'L2', countKey: 'by_l2', distKey: 'by_l2',
    keys: ['sex', 'class2', 'item', 'sesn'],
    fields: ['SEX_NM', 'CLASS2', 'ITEM', 'SESN_SUB_NM'],
    label: 'SEX × CLASS × ITEM × SESN' },
  { key: 'L3', countKey: 'by_l3', distKey: 'by_l3',
    keys: ['sex', 'class2', 'item'],
    fields: ['SEX_NM', 'CLASS2', 'ITEM'],
    label: 'SEX × CLASS × ITEM' },
  { key: 'L4', countKey: 'by_l4', distKey: 'by_l4',
    keys: ['sex', 'class2'],
    fields: ['SEX_NM', 'CLASS2'],
    label: 'SEX × CLASS' },
  { key: 'L5', countKey: 'by_l5', distKey: 'by_l5',
    keys: ['class2'],
    fields: ['CLASS2'],
    label: 'CLASS' },
];

// ----------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------

function sizeIdx(size, sizeOrder) {
  const i = sizeOrder.indexOf(size);
  return i >= 0 ? i : -1;
}

/**
 * 인접 비례 분배 (정책 1, 정책 3 폴백 공용)
 * 양쪽 인접이 둘 다 있으면 5:5, 한쪽만 있으면 100%, 둘 다 비면 한 칸 더 멀리 재귀.
 * Returns: { sizeCD: ratio } — 합계 1
 */
function findAdjacent(missingSize, allowedSet, sizeOrder) {
  const idx = sizeIdx(missingSize, sizeOrder);
  if (idx < 0) {
    const first = [...allowedSet][0];
    return first ? { [first]: 1 } : {};
  }

  let distance = 1;
  while (distance < sizeOrder.length) {
    const leftIdx = idx - distance;
    const rightIdx = idx + distance;
    const left = leftIdx >= 0 ? sizeOrder[leftIdx] : null;
    const right = rightIdx < sizeOrder.length ? sizeOrder[rightIdx] : null;

    const leftIn = left && allowedSet.has(left);
    const rightIn = right && allowedSet.has(right);

    if (leftIn && rightIn) return { [left]: 0.5, [right]: 0.5 };
    if (leftIn) return { [left]: 1 };
    if (rightIn) return { [right]: 1 };
    distance++;
  }
  const first = [...allowedSet][0];
  return first ? { [first]: 1 } : {};
}

/**
 * Step 1. 인접 분배 (정책 1)
 * past_size_sales에서 allowedSet 밖 사이즈의 수요를 인접 신규 사이즈에 분배.
 */
function distributeAdjacent(pastSizeSales, allowedSet, sizeOrder) {
  const sizesToRemove = [];
  for (const [size, qty] of Object.entries(pastSizeSales)) {
    if (allowedSet.has(size)) continue;
    const dist = findAdjacent(size, allowedSet, sizeOrder);
    for (const [target, ratio] of Object.entries(dist)) {
      pastSizeSales[target] = (pastSizeSales[target] || 0) + qty * ratio;
    }
    sizesToRemove.push(size);
  }
  sizesToRemove.forEach(s => { delete pastSizeSales[s]; });
}

/**
 * Step 2. 빈자리 채우기 (정책 3)
 * allowedSet 안인데 past_size_sales[s]=0인 사이즈 → 카테고리 분포에서 가상 비중 부여.
 * 카테고리 분포에서도 0이면 인접 비례 폴백 (α=0.5).
 */
function fillEmptyFromCategoryDist(pastSizeSales, allowedSet, levelDist, sizeOrder) {
  const total = Object.values(pastSizeSales).reduce((a, b) => a + b, 0);
  if (total <= 0) return;

  for (const size of allowedSet) {
    if ((pastSizeSales[size] || 0) > 0) continue;

    const ratio = levelDist?.[size];
    if (ratio && ratio > 0) {
      // 카테고리 분포 비중을 현재 표본 크기로 스케일링
      pastSizeSales[size] = total * ratio;
    } else {
      // 카테고리 분포도 0 → 인접 비례 폴백
      const adj = findAdjacentValueRecursive(size, allowedSet, pastSizeSales, sizeOrder);
      if (adj > 0) pastSizeSales[size] = adj * POLICY3_ALPHA;
    }
  }
}

function findAdjacentValueRecursive(size, allowedSet, sizeSales, sizeOrder) {
  const idx = sizeIdx(size, sizeOrder);
  if (idx < 0) return 0;

  let distance = 1;
  while (distance < sizeOrder.length) {
    const leftIdx = idx - distance;
    const rightIdx = idx + distance;
    const left = leftIdx >= 0 ? sizeOrder[leftIdx] : null;
    const right = rightIdx < sizeOrder.length ? sizeOrder[rightIdx] : null;

    const leftVal = left && allowedSet.has(left) ? (sizeSales[left] || 0) : 0;
    const rightVal = right && allowedSet.has(right) ? (sizeSales[right] || 0) : 0;

    if (leftVal > 0 && rightVal > 0) return (leftVal + rightVal) / 2;
    if (leftVal > 0) return leftVal;
    if (rightVal > 0) return rightVal;
    distance++;
  }
  return 0;
}

/**
 * Step 3. 정규화 + 배분 (정책 2 마무리)
 * 합 = confirmed_qty, 10단위 반올림, 잔여분은 최대 비중 사이즈에 가산.
 */
function normalize(pastSizeSales, allowedSet, confirmedQty, sizeOrder) {
  // allowedSet 밖 정리 + 음수 방지
  const finalSales = {};
  for (const [size, qty] of Object.entries(pastSizeSales)) {
    if (allowedSet && !allowedSet.has(size)) continue;
    if (qty > 0) finalSales[size] = qty;
  }

  const total = Object.values(finalSales).reduce((a, b) => a + b, 0);
  if (total <= 0) {
    // 균등 분배 폴백
    const sizes = allowedSet ? [...allowedSet] : Object.keys(finalSales);
    if (sizes.length === 0) return { sizes: {}, ratios: {} };
    const per = Math.floor(confirmedQty / sizes.length);
    const remainder = confirmedQty - per * sizes.length;
    const result = {};
    sizes.forEach((s, i) => { result[s] = per + (i === 0 ? remainder : 0); });
    return { sizes: result, ratios: Object.fromEntries(sizes.map(s => [s, 1 / sizes.length])) };
  }

  const ratios = {};
  const sizes = {};
  for (const [size, qty] of Object.entries(finalSales)) {
    ratios[size] = qty / total;
    sizes[size] = Math.round((confirmedQty * ratios[size]) / 10) * 10;
  }

  // 잔여분 보정 — 최대 비중 사이즈에 가산
  const allocated = Object.values(sizes).reduce((a, b) => a + b, 0);
  const diff = confirmedQty - allocated;
  if (diff !== 0 && Object.keys(sizes).length > 0) {
    const maxSize = Object.entries(ratios).reduce((a, b) => b[1] > a[1] ? b : a)[0];
    sizes[maxSize] += diff;
  }

  return { sizes, ratios };
}

// ----------------------------------------------------------------------
// Main: 매칭 폴백 + Step 1~3
// ----------------------------------------------------------------------

/**
 * matchInput: {
 *   sex:    '남성' | '여성' | '공용' | '아동' | null,
 *   class2: 'Outer' | 'Inner' | 'Bottom' | ...,
 *   item:   'PD' | 'DJ' | 'MT' | ...,
 *   sesn:   'Fall' | 'Winter' | ... | null,
 *   fit:    'Regular' | 'Slim' | ... | null,
 *   sizeRange: 'XS,S,M,L,XL' | null,
 *   confirmedQty: number,
 * }
 *
 * ctx: {
 *   allData:        [...salesData, ...prevData] (당해+전년 통합),
 *   sampleCount:    { by_l1: {group_label: SC_count}, ... },
 *   categoryDist:   { by_l1: {group_label: {size: ratio}}, ... },
 *   sizeOrder:      ['XS', 'S', 'M', ...],
 * }
 */
export function computeSizeDistribution(matchInput, ctx) {
  const { sex, class2, item, sesn, fit, sizeRange, confirmedQty } = matchInput;
  const { allData, sampleCount, categoryDist, sizeOrder } = ctx;

  if (!confirmedQty || confirmedQty <= 0) {
    return { matchLevel: 'NONE', matchLabel: '-', sizes: {}, ratios: {}, warning: true };
  }

  // FIT Null이면 L1 스킵 (§8.3)
  const startLevel = (!fit || fit === null) ? 1 : 0;

  let matchLevel = null;
  let matchLabel = '-';
  let groupLabel = '';
  let matched = [];
  let levelDist = null;

  for (let i = startLevel; i < LEVEL_CONFIG.length; i++) {
    const L = LEVEL_CONFIG[i];
    const groupParts = L.keys.map(k => matchInput[k]);
    // 필수 키 중 빈 값 있으면 스킵
    if (groupParts.some(v => v === null || v === undefined || v === '')) continue;

    const gLabel = groupParts.join('|');
    const sc = sampleCount?.[L.countKey]?.[gLabel] || 0;

    // 표본 부족 시 다음 Level로 (단, L5 마지막에서는 통과)
    if (sc < SC_THRESHOLD && i < LEVEL_CONFIG.length - 1) continue;

    // 매칭 행 필터링
    const filtered = (allData || []).filter(d =>
      L.fields.every((field, idx) => d[field] === groupParts[idx])
    );

    if (filtered.length > 0) {
      matched = filtered;
      matchLevel = L.key;
      matchLabel = L.label;
      groupLabel = gLabel;
      levelDist = categoryDist?.[L.distKey]?.[gLabel] || null;
      break;
    }
  }

  if (!matched.length) {
    return { matchLevel: 'NONE', matchLabel: '-', sizes: {}, ratios: {}, warning: true };
  }

  // 사이즈별 SALE_QTY 집계
  const pastSizeSales = {};
  matched.forEach(d => {
    if (!d.SIZE_CD) return;
    pastSizeSales[d.SIZE_CD] = (pastSizeSales[d.SIZE_CD] || 0) + (d.SALE_QTY || 0);
  });

  // size_range 파싱
  const allowedSet = sizeRange
    ? new Set(sizeRange.split(/[,\/]/).map(s => s.trim()).filter(Boolean))
    : null;

  // Step 1: 인접 분배 (size_range 밖 → 인접)
  if (allowedSet) {
    distributeAdjacent(pastSizeSales, allowedSet, sizeOrder);
  }

  // Step 2: 빈자리 채우기 (size_range 내 비중 0 → 카테고리 분포)
  if (allowedSet && levelDist) {
    fillEmptyFromCategoryDist(pastSizeSales, allowedSet, levelDist, sizeOrder);
  }

  // Step 3: 정규화 + 배분
  const result = normalize(pastSizeSales, allowedSet, confirmedQty, sizeOrder);

  return {
    matchLevel,
    matchLabel,
    groupLabel,
    sizes: result.sizes,
    ratios: result.ratios,
    warning: false,
  };
}
