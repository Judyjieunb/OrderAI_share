import React, { useState, useMemo, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext.jsx';
import { useBrandSeason } from '../contexts/BrandSeasonContext.jsx';
import { createApiClient } from '../service/apiClient.js';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LabelList, Legend } from 'recharts';
import { Filter, Calculator, X, List, Package, Download, AlertTriangle } from 'lucide-react';
import { publicUrl } from '../utils/api.js';
import ResetButton from './common/ResetButton.jsx';
import { CHANGED_CELL_CLASS } from '../utils/highlight.js';

const ITEM_CODE_MAP = {
  '니트가디건': 'KC', '니트풀오버': 'KP', '다운베스트': 'DV', '다운점퍼': 'DJ',
  '데님셔츠': 'DR', '맨투맨': 'MT', '반팔카라티셔츠': 'TS', '방풍자켓': 'WJ',
  '스커트': 'SK', '우븐셔츠': 'WS', '우븐팬츠': 'WP', '원피스': 'OP',
  '점퍼': 'JP', '진바지': 'DP', '진스커트': 'DS', '진자켓': 'DK',
  '트레이닝(상의)': 'TR', '패딩': 'PD', '팬츠': 'PT', '폴라폴리스점퍼': 'FD', '후드티': 'HD',
};
const toItemCode = (nm) => ITEM_CODE_MAP[nm] || nm;

const colorRangeBadge = (range) => {
  const map = {
    BLACK:   'bg-gray-200/60 text-gray-700',
    WHITE:   'bg-gray-100/60 text-gray-500 border border-gray-200',
    GRAY:    'bg-gray-200/50 text-gray-600',
    NAVY:    'bg-indigo-100/60 text-indigo-600',
    BLUE:    'bg-blue-100/60 text-blue-600',
    RED:     'bg-red-100/60 text-red-500',
    PINK:    'bg-pink-100/60 text-pink-500',
    ORANGE:  'bg-orange-100/60 text-orange-500',
    YELLOW:  'bg-yellow-100/60 text-yellow-600',
    GREEN:   'bg-green-100/60 text-green-600',
    PURPLE:  'bg-purple-100/60 text-purple-500',
    BROWN:   'bg-amber-100/60 text-amber-700',
    BEIGE:   'bg-amber-50/60 text-amber-600',
    SPECIAL: 'bg-violet-100/60 text-violet-500',
  };
  return map[range] || 'bg-gray-100/60 text-gray-500';
};

const colorDotStyle = (range) => {
  const map = {
    BLACK:   'bg-gray-800 border-gray-900',
    WHITE:   'bg-white border-gray-300',
    GRAY:    'bg-gray-400 border-gray-500',
    NAVY:    'bg-indigo-900 border-indigo-950',
    BLUE:    'bg-blue-500 border-blue-600',
    RED:     'bg-red-400 border-red-500',
    PINK:    'bg-pink-300 border-pink-400',
    ORANGE:  'bg-orange-400 border-orange-500',
    YELLOW:  'bg-yellow-300 border-yellow-400',
    GREEN:   'bg-green-500 border-green-600',
    PURPLE:  'bg-purple-400 border-purple-500',
    BROWN:   'bg-amber-700 border-amber-800',
    BEIGE:   'bg-amber-200 border-amber-300',
    SPECIAL: 'bg-gradient-to-br from-pink-400 to-violet-400 border-violet-500',
  };
  return map[range] || 'bg-gray-300 border-gray-400';
};

// ----------------------------------------------------------------------
// Helper: Color Mapping Modal
// ----------------------------------------------------------------------
const ColorMappingModal = ({ isOpen, onClose, data }) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="p-5 border-b border-gray-100 flex justify-between items-center">
          <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <List className="w-5 h-5 text-blue-600" />
            컬러 그룹핑 기준 (Color Mapping)
          </h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-full text-gray-500"><X className="w-6 h-6" /></button>
        </div>
        <div className="overflow-y-auto p-5">
          <table className="w-full text-sm text-left border-collapse">
            <thead className="bg-gray-50 text-gray-500 font-medium sticky top-0">
              <tr>
                <th className="px-4 py-2 border-b">컬러코드</th>
                <th className="px-4 py-2 border-b">컬러명</th>
                <th className="px-4 py-2 border-b">컬러레인지 그룹</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {Array.isArray(data) && data.map((item, idx) => (
                <tr key={idx} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono text-gray-600">{item.컬러코드}</td>
                  <td className="px-4 py-2 text-gray-900">{item.컬러명}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-1 rounded-md text-xs font-semibold ${colorRangeBadge(item.COLOR_RANGE)}`}>{item.COLOR_RANGE}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="p-4 border-t border-gray-100 bg-gray-50 rounded-b-xl flex justify-end">
          <button onClick={onClose} className="px-4 py-2 bg-white border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium text-sm">닫기</button>
        </div>
      </div>
    </div>
  );
};

// 스타일코드 2번째 문자로 성별 판별: A=공용, F=여성, L=남성
const sexFromStyleCd = (partCd) => {
  if (!partCd || partCd.length < 2) return '';
  const code = partCd[1].toUpperCase();
  return { A: '공용', F: '여성', L: '남성' }[code] || '';
};

// ----------------------------------------------------------------------
// Helper: Size Distribution Modal (Step 4 → 5 연동)
// ----------------------------------------------------------------------
const SizeDistributionModal = ({ isOpen, onClose, orders, salesData, prevData, colorMapping, sizeOrder }) => {
  if (!isOpen || !orders) return null;

  // color_cd[-3:] → colorMapping → COLOR_RANGE 매핑
  const getColorRange = (colorCd) => {
    if (!colorCd || colorCd === '-') return null;
    const suffix = colorCd.replace(/^[0-9]+/, '');  // 숫자 접두사 제거 (50BKS → BKS)
    const match = colorMapping.find(m => m.컬러코드 === suffix);
    return match?.COLOR_RANGE || null;
  };

  // 2개년 통합 사이즈 배분 계산
  const allSalesData = [...salesData, ...prevData];

  const computeDistribution = (order) => {
    const { class2, new_item_nm, color_cd, confirmed_qty, size_range, new_part_cd } = order;
    const colorRange = getColorRange(color_cd);
    const itemCode = toItemCode(new_item_nm);
    const sex = sexFromStyleCd(new_part_cd);

    // size_range 파싱: "S,M,L,XL" → Set(['S','M','L','XL'])
    const allowedSizes = size_range
      ? new Set(size_range.split(/[,\/]/).map(s => s.trim()).filter(Boolean))
      : null;

    // 성별 필터: sex가 있으면 해당 성별 데이터 우선, 없으면 전체
    const sexFiltered = sex
      ? allSalesData.filter(d => d.SEX_NM === sex)
      : allSalesData;
    // 성별 필터 후 데이터가 없으면 전체 데이터로 폴백
    const pool = sexFiltered.length > 0 ? sexFiltered : allSalesData;

    // 폴백 계층 매칭 (ITEM 코드 기준)
    let matched = [];
    let matchLevel = '';

    // Level 1: CLASS2 + ITEM + COLOR_RANGE
    if (colorRange && itemCode) {
      matched = pool.filter(d =>
        d.CLASS2 === class2 && d.ITEM === itemCode && d.COLOR_RANGE === colorRange
      );
      if (matched.length > 0) matchLevel = 'L1';
    }

    // Level 2: CLASS2 + COLOR_RANGE
    if (matched.length === 0 && colorRange) {
      matched = pool.filter(d =>
        d.CLASS2 === class2 && d.COLOR_RANGE === colorRange
      );
      if (matched.length > 0) matchLevel = 'L2';
    }

    // Level 3: CLASS2 + ITEM
    if (matched.length === 0 && itemCode) {
      matched = pool.filter(d =>
        d.CLASS2 === class2 && d.ITEM === itemCode
      );
      if (matched.length > 0) matchLevel = 'L3';
    }

    // Level 4: CLASS2 전체
    if (matched.length === 0) {
      matched = pool.filter(d => d.CLASS2 === class2);
      if (matched.length > 0) matchLevel = 'L4';
    }

    // 매칭 불가
    if (matched.length === 0) {
      return { colorRange, matchLevel: 'NONE', sexMatched: false, sizes: {}, warning: true };
    }

    // SIZE_CD별 SALE_QTY 합산
    const sizeSales = {};
    matched.forEach(d => {
      // size_range 필터: 허용 사이즈만 집계
      if (allowedSizes && !allowedSizes.has(d.SIZE_CD)) return;
      sizeSales[d.SIZE_CD] = (sizeSales[d.SIZE_CD] || 0) + (d.SALE_QTY || 0);
    });

    // size_range 지정인데 실적 매칭 없는 사이즈 → 균등 배분 폴백
    if (allowedSizes && Object.keys(sizeSales).length === 0) {
      const sizes = [...allowedSizes];
      const perSize = Math.floor(confirmed_qty / sizes.length);
      const remainder = confirmed_qty - perSize * sizes.length;
      const rawQtys = {};
      const ratios = {};
      sizes.forEach((s, i) => {
        rawQtys[s] = perSize + (i === 0 ? remainder : 0);
        ratios[s] = 1 / sizes.length;
      });
      return { colorRange, matchLevel, sexMatched: pool !== allSalesData, sizes: rawQtys, ratios, warning: false };
    }

    const totalSale = Object.values(sizeSales).reduce((s, v) => s + v, 0);
    if (totalSale === 0) {
      return { colorRange, matchLevel, sexMatched: pool !== allSalesData, sizes: {}, warning: true };
    }

    // 비중 계산 → 반올림 배분
    const ratios = {};
    const rawQtys = {};
    for (const [size, sale] of Object.entries(sizeSales)) {
      ratios[size] = sale / totalSale;
      rawQtys[size] = Math.round(confirmed_qty * ratios[size]);
    }

    // 잔여분 보정 → 최대비중 사이즈
    const allocated = Object.values(rawQtys).reduce((s, v) => s + v, 0);
    const diff = confirmed_qty - allocated;
    if (diff !== 0) {
      const maxSize = Object.entries(ratios).reduce((a, b) => b[1] > a[1] ? b : a)[0];
      rawQtys[maxSize] += diff;
    }

    return { colorRange, matchLevel, sexMatched: pool !== allSalesData, sizes: rawQtys, ratios, warning: false };
  };

  // 모든 주문에 대해 배분 계산
  const distributions = orders.map(order => ({
    ...order,
    dist: computeDistribution(order),
  }));

  // 모든 사이즈 수집 (정렬)
  const allSizes = [...new Set(distributions.flatMap(d => Object.keys(d.dist.sizes)))];
  const sizeIdx = (s) => { const i = sizeOrder.indexOf(s); return i >= 0 ? i : 999; };
  allSizes.sort((a, b) => sizeIdx(a) - sizeIdx(b));

  // 하단 합계
  const sizeTotals = {};
  allSizes.forEach(s => { sizeTotals[s] = 0; });
  distributions.forEach(d => {
    allSizes.forEach(s => { sizeTotals[s] += d.dist.sizes[s] || 0; });
  });
  const grandTotal = Object.values(sizeTotals).reduce((s, v) => s + v, 0);

  // Excel Export
  const handleExcelExport = async () => {
    const XLSX = await import('xlsx');
    const rows = distributions.map(d => {
      const row = {
        '복종': d.class2,
        '아이템': toItemCode(d.new_item_nm) || '-',
        '스타일코드': d.new_part_cd,
        '컬러코드': d.color_cd,
        '확정수량': d.confirmed_qty,
        '매칭레벨': d.dist.matchLevel,
      };
      allSizes.forEach(s => { row[s] = d.dist.sizes[s] || 0; });
      return row;
    });
    // 합계 행
    const totalRow = { '복종': '합계', '아이템': '', '스타일코드': '', '컬러코드': '', '확정수량': distributions.reduce((s, d) => s + d.confirmed_qty, 0), '매칭레벨': '' };
    allSizes.forEach(s => { totalRow[s] = sizeTotals[s]; });
    rows.push(totalRow);

    const ws = XLSX.utils.json_to_sheet(rows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, '사이즈배분');
    const season = orders[0]?.season || '26F';
    XLSX.writeFile(wb, `${season}_사이즈배분.xlsx`);
  };

  const matchBadge = (level, sexMatched) => {
    const cls = {
      L1: 'bg-green-100 text-green-700',
      L2: 'bg-yellow-100 text-yellow-700',
      L3: 'bg-blue-100 text-blue-700',
      L4: 'bg-orange-100 text-orange-700',
    }[level] || 'bg-red-100 text-red-700';
    const base = {
      L1: 'CLASS × ITEM × COLOR',
      L2: 'CLASS × COLOR',
      L3: 'CLASS × ITEM',
      L4: 'CLASS',
    }[level];
    if (!base) return <span className={`px-1.5 py-0.5 text-[10px] font-medium ${cls} rounded flex items-center gap-0.5`}><AlertTriangle className="w-3 h-3" />불가</span>;
    const label = sexMatched ? `SEX × ${base}` : base;
    return <span className={`px-1.5 py-0.5 text-[10px] font-medium ${cls} rounded`}>{label}</span>;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-[95vw] max-h-[85vh] flex flex-col">
        <div className="p-5 border-b border-gray-100 flex justify-between items-center shrink-0">
          <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <Package className="w-5 h-5 text-blue-600" />
            사이즈 배분 결과
            <span className="text-sm font-normal text-gray-500">({distributions.length}건)</span>
          </h3>
          <div className="flex items-center gap-2">
            <button
              onClick={handleExcelExport}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Excel 다운로드
            </button>
            <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-full text-gray-500"><X className="w-6 h-6" /></button>
          </div>
        </div>
        <div className="overflow-auto flex-1 p-1">
          <table className="w-full text-xs text-left border-collapse table-fixed">
            <thead className="bg-gray-50 text-gray-500 font-medium sticky top-0 z-10">
              <tr>
                <th className="w-[6%] px-2 py-2 border-b whitespace-nowrap">복종</th>
                <th className="w-[5%] px-2 py-2 border-b whitespace-nowrap">아이템</th>
                <th className="w-[10%] px-2 py-2 border-b whitespace-nowrap">스타일코드</th>
                <th className="w-[7%] px-2 py-2 border-b whitespace-nowrap">컬러코드</th>
                <th className="w-[14%] px-2 py-2 border-b whitespace-nowrap">매칭</th>
                <th className="w-[7%] px-2 py-2 border-b text-right whitespace-nowrap">확정수량</th>
                {allSizes.map(s => (
                  <th key={s} style={{ width: `${51 / allSizes.length}%` }} className="px-2 py-2 border-b text-right whitespace-nowrap bg-blue-50">{s}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {distributions.map((d, idx) => {
                const isFirstOfStyle = idx === 0 || distributions[idx - 1].new_part_cd !== d.new_part_cd;
                const styleRowCount = isFirstOfStyle ? distributions.filter(x => x.new_part_cd === d.new_part_cd).length : 0;
                return (
                <tr key={idx} className={`hover:bg-gray-50 ${d.dist.warning ? 'bg-red-50/30' : ''} ${isFirstOfStyle && idx > 0 ? 'border-t-2 border-gray-200' : ''}`}>
                  {isFirstOfStyle ? (
                    <>
                      <td rowSpan={styleRowCount} className="px-2 py-2 text-gray-600 align-top border-r border-gray-100">{d.class2}</td>
                      <td rowSpan={styleRowCount} className="px-2 py-2 text-gray-600 align-top border-r border-gray-100">{toItemCode(d.new_item_nm) || '-'}</td>
                      <td rowSpan={styleRowCount} className="px-2 py-2 font-mono font-semibold text-gray-800 align-top border-r border-gray-100">{d.new_part_cd}</td>
                    </>
                  ) : null}
                  <td className="px-2 py-2 font-mono text-gray-600">{d.color_cd}</td>
                  <td className="px-2 py-2">{matchBadge(d.dist.matchLevel, d.dist.sexMatched)}</td>
                  <td className="px-2 py-2 text-right font-bold text-gray-900">{d.confirmed_qty.toLocaleString()}</td>
                  {allSizes.map(s => {
                    const hasValue = d.dist.sizes[s] && d.dist.sizes[s] > 0;
                    return (
                      <td key={s} className={`px-2 py-2 text-right tabular-nums ${hasValue ? 'bg-blue-50/30' : 'bg-gray-100'}`}>
                        {hasValue ? d.dist.sizes[s].toLocaleString() : <span className="text-gray-300">-</span>}
                      </td>
                    );
                  })}
                </tr>
                );
              })}
            </tbody>
            <tfoot className="bg-gray-100 border-t-2 border-gray-200 font-bold text-gray-800 sticky bottom-0">
              <tr>
                <td className="px-2 py-2.5" colSpan={5}>합계</td>
                <td className="px-2 py-2.5 text-right">{grandTotal.toLocaleString()}</td>
                {allSizes.map(s => (
                  <td key={s} className="px-2 py-2.5 text-right tabular-nums bg-blue-50/50">
                    {sizeTotals[s]?.toLocaleString() || 0}
                  </td>
                ))}
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  );
};

// ----------------------------------------------------------------------
// Main Component
// ----------------------------------------------------------------------
export default function SizeAssortment() {
  const { user } = useAuth();
  const { brand, season } = useBrandSeason();
  const api = useMemo(
    () => createApiClient(user?.email, brand, season, user?.role),
    [user?.email, brand, season],
  );
  const [salesData, setSalesData] = useState([]);
  const [prevData, setPrevData] = useState([]);
  const [meta, setMeta] = useState({});
  const [colorMapping, setColorMapping] = useState([]);
  const [dataSource, setDataSource] = useState('sample');
  const [showColorModal, setShowColorModal] = useState(false);

  // Filters
  const [selSex, setSelSex] = useState('All');
  const [selClass, setSelClass] = useState('All');
  const [selCat, setSelCat] = useState('All');
  const [selItemNm, setSelItemNm] = useState('All');
  const [selColorRanges, setSelColorRanges] = useState(new Set()); // empty = All
  const [showColorPicker, setShowColorPicker] = useState(false);

  // View mode
  const [viewMode, setViewMode] = useState('current'); // current | prev | compare

  // Order allocation
  const [totalOrderQty, setTotalOrderQty] = useState('');

  // Simulation
  const [isSimMode, setIsSimMode] = useState(false);
  const [excludedSizes, setExcludedSizes] = useState(new Set());
  const [mirrorPrev, setMirrorPrev] = useState(false);

  // Size Distribution Modal (Step 4→5 연동)
  const [showSizeDistModal, setShowSizeDistModal] = useState(false);
  const [confirmedOrders, setConfirmedOrders] = useState(null);
  const [sizeDistError, setSizeDistError] = useState(null);

  // Load pipeline data
  useEffect(() => {
    api.fetchFile('size_assortment_data.json')
      .then(data => {
        if (!data) return;
        if (data.salesData?.length > 0) { setSalesData(data.salesData); setDataSource('json'); }
        if (data.prevData?.length > 0) setPrevData(data.prevData);
        if (data.colorMapping?.length > 0) setColorMapping(data.colorMapping);
        if (data.meta) setMeta(data.meta);
      })
      .catch(() => {});
  }, [api]);

  // 사이즈 배분 버튼 클릭
  const handleOpenSizeDist = () => {
    setSizeDistError(null);
    api.fetchFile('confirmed_order_data.json')
      .then(data => {
        if (!data) throw new Error('Step 4에서 수량을 확정해주세요.');
        if (!data.orders || data.orders.length === 0) {
          throw new Error('확정된 수량이 없습니다. Step 4에서 수량을 확정해주세요.');
        }
        setConfirmedOrders(data.orders);
        setShowSizeDistModal(true);
      })
      .catch(err => setSizeDistError(err.message));
  };

  // 엑셀 직접 다운로드 (모달 없이)
  const handleDirectExcelExport = async () => {
    setSizeDistError(null);
    try {
      const data = await api.fetchFile('confirmed_order_data.json');
      if (!data) throw new Error('Step 4에서 수량을 확정해주세요.');
      if (!data.orders || data.orders.length === 0) {
        throw new Error('확정된 수량이 없습니다.');
      }
      const orders = data.orders;

      // 배분 로직 (SizeDistributionModal과 동일)
      const getColorRange = (colorCd) => {
        if (!colorCd || colorCd === '-') return null;
        const suffix = colorCd.replace(/^[0-9]+/, '');
        const match = colorMapping.find(m => m.컬러코드 === suffix);
        return match?.COLOR_RANGE || null;
      };
      const allSalesData = [...salesData, ...prevData];
      const sOrder = meta?.sizeOrder || ['XS','S','M','L','XL','XXL','2XL'];

      const computeDist = (order) => {
        const { class2, new_item_nm, color_cd, confirmed_qty, size_range, new_part_cd } = order;
        const colorRange = getColorRange(color_cd);
        const itemCode = toItemCode(new_item_nm);
        const sex = sexFromStyleCd(new_part_cd);
        const allowedSizes = size_range
          ? new Set(size_range.split(/[,\/]/).map(s => s.trim()).filter(Boolean))
          : null;
        const sexFiltered = sex ? allSalesData.filter(d => d.SEX_NM === sex) : allSalesData;
        const pool = sexFiltered.length > 0 ? sexFiltered : allSalesData;
        let matched = [], matchLevel = '';

        if (colorRange && itemCode) {
          matched = pool.filter(d => d.CLASS2 === class2 && d.ITEM === itemCode && d.COLOR_RANGE === colorRange);
          if (matched.length > 0) matchLevel = 'L1';
        }
        if (!matched.length && colorRange) {
          matched = pool.filter(d => d.CLASS2 === class2 && d.COLOR_RANGE === colorRange);
          if (matched.length > 0) matchLevel = 'L2';
        }
        if (!matched.length && itemCode) {
          matched = pool.filter(d => d.CLASS2 === class2 && d.ITEM === itemCode);
          if (matched.length > 0) matchLevel = 'L3';
        }
        if (!matched.length) {
          matched = pool.filter(d => d.CLASS2 === class2);
          if (matched.length > 0) matchLevel = 'L4';
        }
        if (!matched.length) return { sizes: {}, matchLevel: 'NONE' };

        const sizeSales = {};
        matched.forEach(d => {
          if (allowedSizes && !allowedSizes.has(d.SIZE_CD)) return;
          sizeSales[d.SIZE_CD] = (sizeSales[d.SIZE_CD] || 0) + (d.SALE_QTY || 0);
        });
        // size_range 지정인데 실적 매칭 없는 사이즈 → 균등 배분 폴백
        if (allowedSizes && Object.keys(sizeSales).length === 0) {
          const sizes = [...allowedSizes];
          const perSize = Math.floor(confirmed_qty / sizes.length);
          const remainder = confirmed_qty - perSize * sizes.length;
          const rawQtys = {};
          sizes.forEach((s, i) => { rawQtys[s] = perSize + (i === 0 ? remainder : 0); });
          return { sizes: rawQtys, matchLevel };
        }
        const totalSale = Object.values(sizeSales).reduce((s, v) => s + v, 0);
        if (totalSale === 0) return { sizes: {}, matchLevel };

        const rawQtys = {};
        let maxRatio = 0, maxSize = '';
        for (const [size, sale] of Object.entries(sizeSales)) {
          const ratio = sale / totalSale;
          rawQtys[size] = Math.round(confirmed_qty * ratio);
          if (ratio > maxRatio) { maxRatio = ratio; maxSize = size; }
        }
        const diff = confirmed_qty - Object.values(rawQtys).reduce((s, v) => s + v, 0);
        if (diff !== 0 && maxSize) rawQtys[maxSize] += diff;
        return { sizes: rawQtys, matchLevel };
      };

      const distributions = orders.map(o => ({ ...o, dist: computeDist(o) }));
      const allSizes = [...new Set(distributions.flatMap(d => Object.keys(d.dist.sizes)))];
      const sizeIdx = (s) => { const i = sOrder.indexOf(s); return i >= 0 ? i : 999; };
      allSizes.sort((a, b) => sizeIdx(a) - sizeIdx(b));

      const sizeTotals = {};
      allSizes.forEach(s => { sizeTotals[s] = 0; });
      distributions.forEach(d => { allSizes.forEach(s => { sizeTotals[s] += d.dist.sizes[s] || 0; }); });

      const XLSX = await import('xlsx');
      const rows = distributions.map(d => {
        const row = { '복종': d.class2, '아이템': toItemCode(d.new_item_nm) || '-', '스타일코드': d.new_part_cd, '컬러코드': d.color_cd, '확정수량': d.confirmed_qty, '매칭레벨': d.dist.matchLevel };
        allSizes.forEach(s => { row[s] = d.dist.sizes[s] || 0; });
        return row;
      });
      const totalRow = { '복종': '합계', '아이템': '', '스타일코드': '', '컬러코드': '', '확정수량': distributions.reduce((s, d) => s + d.confirmed_qty, 0), '매칭레벨': '' };
      allSizes.forEach(s => { totalRow[s] = sizeTotals[s]; });
      rows.push(totalRow);

      const ws = XLSX.utils.json_to_sheet(rows);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, '사이즈배분');
      const season = data.season || '26F';
      XLSX.writeFile(wb, `${season}_사이즈배분.xlsx`);
    } catch (err) {
      setSizeDistError(err.message);
    }
  };

  // Cascading filter options
  const filterData = (data) => {
    let d = data;
    if (selSex !== 'All') d = d.filter(r => r.SEX_NM === selSex);
    if (selClass !== 'All') d = d.filter(r => r.CLASS2 === selClass);
    if (selCat !== 'All') d = d.filter(r => r.CAT_NM === selCat);
    if (selItemNm !== 'All') d = d.filter(r => r.ITEM_NM === selItemNm);
    if (selColorRanges.size > 0) d = d.filter(r => selColorRanges.has(r.COLOR_RANGE));
    return d;
  };

  const allData = useMemo(() => [...salesData, ...prevData], [salesData, prevData]);

  const sexOptions = useMemo(() => ['All', ...new Set(allData.map(d => d.SEX_NM))], [allData]);

  const classOptions = useMemo(() => {
    let d = allData;
    if (selSex !== 'All') d = d.filter(r => r.SEX_NM === selSex);
    return ['All', ...new Set(d.map(r => r.CLASS2))];
  }, [allData, selSex]);

  const catOptions = useMemo(() => {
    let d = allData;
    if (selSex !== 'All') d = d.filter(r => r.SEX_NM === selSex);
    if (selClass !== 'All') d = d.filter(r => r.CLASS2 === selClass);
    return ['All', ...new Set(d.map(r => r.CAT_NM))];
  }, [allData, selSex, selClass]);

  const itemNmOptions = useMemo(() => {
    let d = allData;
    if (selSex !== 'All') d = d.filter(r => r.SEX_NM === selSex);
    if (selClass !== 'All') d = d.filter(r => r.CLASS2 === selClass);
    if (selCat !== 'All') d = d.filter(r => r.CAT_NM === selCat);
    return ['All', ...new Set(d.map(r => r.ITEM_NM).filter(Boolean))];
  }, [allData, selSex, selClass, selCat]);

  const colorRangeOptions = useMemo(() => {
    let d = allData;
    if (selSex !== 'All') d = d.filter(r => r.SEX_NM === selSex);
    if (selClass !== 'All') d = d.filter(r => r.CLASS2 === selClass);
    if (selCat !== 'All') d = d.filter(r => r.CAT_NM === selCat);
    if (selItemNm !== 'All') d = d.filter(r => r.ITEM_NM === selItemNm);
    return ['All', ...new Set(d.map(r => r.COLOR_RANGE).filter(Boolean))].sort();
  }, [allData, selSex, selClass, selCat, selItemNm]);

  // Reset child filters on parent change
  const handleSexChange = (v) => { setSelSex(v); setSelClass('All'); setSelCat('All'); setSelItemNm('All'); setSelColorRanges(new Set()); };
  const handleClassChange = (v) => { setSelClass(v); setSelCat('All'); setSelItemNm('All'); setSelColorRanges(new Set()); };
  const handleCatChange = (v) => { setSelCat(v); setSelItemNm('All'); setSelColorRanges(new Set()); };
  const handleItemNmChange = (v) => { setSelItemNm(v); setSelColorRanges(new Set()); };

  // Size order helper
  const sizeOrder = meta.sizeOrder || ['XS','S','M','L','XL','XXL','2XL'];
  const sizeIndex = (s) => { const idx = sizeOrder.indexOf(s); return idx >= 0 ? idx : 999; };

  // Aggregate by size
  const aggregate = (data) => {
    const grouped = {};
    data.forEach(d => {
      if (!grouped[d.SIZE_CD]) grouped[d.SIZE_CD] = { order: 0, sale: 0 };
      grouped[d.SIZE_CD].order += (d.ORDER_QTY || 0);
      grouped[d.SIZE_CD].sale += (d.SALE_QTY || 0);
    });
    return grouped;
  };

  // Chart data
  const { chartData, topSize } = useMemo(() => {
    const filteredCurrent = filterData(salesData);
    const filteredPrev = filterData(prevData);
    const aggCurrent = aggregate(filteredCurrent);
    const aggPrev = aggregate(filteredPrev);

    // Collect all sizes from both periods
    const allSizes = [...new Set([...Object.keys(aggCurrent), ...Object.keys(aggPrev)])]
      .sort((a, b) => sizeIndex(a) - sizeIndex(b));

    const totalCurrentSale = Object.values(aggCurrent).reduce((s, v) => s + v.sale, 0);
    const totalPrevSale = Object.values(aggPrev).reduce((s, v) => s + v.sale, 0);

    // Combined (2개년 통합)
    const aggCombined = {};
    allSizes.forEach(s => {
      aggCombined[s] = {
        order: (aggCurrent[s]?.order || 0) + (aggPrev[s]?.order || 0),
        sale: (aggCurrent[s]?.sale || 0) + (aggPrev[s]?.sale || 0),
      };
    });
    const totalCombinedSale = Object.values(aggCombined).reduce((s, v) => s + v.sale, 0);

    // Simulation: exclude sizes, redistribute, mirror
    let simCurrentShares = {};
    if (isSimMode) {
      const activeSizes = allSizes.filter(s => !excludedSizes.has(s));
      let baseSales = {};
      // 시뮬 기준: viewMode에 따라 당해/전년/통합 사용
      activeSizes.forEach(s => {
        if (viewMode === 'combined') baseSales[s] = aggCombined[s]?.sale || 0;
        else baseSales[s] = aggCurrent[s]?.sale || 0;
      });

      if (mirrorPrev && totalPrevSale > 0) {
        const baseTotal = Object.values(baseSales).reduce((a, b) => a + b, 0);
        activeSizes.forEach(s => {
          if ((baseSales[s] || 0) === 0 && aggPrev[s]?.sale > 0) {
            baseSales[s] = (aggPrev[s].sale / totalPrevSale) * (baseTotal || 1);
          }
        });
      }

      const simTotal = Object.values(baseSales).reduce((a, b) => a + b, 0);
      activeSizes.forEach(s => {
        simCurrentShares[s] = simTotal > 0 ? baseSales[s] / simTotal : 0;
      });
    }

    let maxSize = null;
    let maxShare = 0;

    const data = allSizes.map(size => {
      const cSale = aggCurrent[size]?.sale || 0;
      const cOrder = aggCurrent[size]?.order || 0;
      const pSale = aggPrev[size]?.sale || 0;
      const pOrder = aggPrev[size]?.order || 0;
      const cbSale = aggCombined[size]?.sale || 0;
      const cbOrder = aggCombined[size]?.order || 0;
      const cShare = totalCurrentSale > 0 ? cSale / totalCurrentSale : 0;
      const pShare = totalPrevSale > 0 ? pSale / totalPrevSale : 0;
      const cbShare = totalCombinedSale > 0 ? cbSale / totalCombinedSale : 0;
      const simShare = isSimMode ? (simCurrentShares[size] || 0) : null;

      let displayShare;
      if (isSimMode) displayShare = simShare || 0;
      else if (viewMode === 'combined') displayShare = cbShare;
      else if (viewMode === 'prev') displayShare = pShare;
      else displayShare = cShare;
      if (displayShare > maxShare) { maxShare = displayShare; maxSize = size; }

      return {
        size,
        currentSale: cSale, currentOrder: cOrder, currentShare: cShare,
        prevSale: pSale, prevOrder: pOrder, prevShare: pShare,
        combinedSale: cbSale, combinedOrder: cbOrder, combinedShare: cbShare,
        simShare,
        excluded: excludedSizes.has(size),
      };
    });

    return { chartData: data, topSize: maxSize ? { size: maxSize, share: maxShare } : null };
  }, [salesData, prevData, selSex, selClass, selCat, selItemNm, selColorRanges, isSimMode, excludedSizes, mirrorPrev, sizeOrder]);

  // Order allocation: 총수량 → 비중별 5단위 배분
  const allocatedOrders = useMemo(() => {
    const total = Number(totalOrderQty);
    if (!total || total <= 0 || chartData.length === 0) return {};

    const activeRows = chartData.filter(d => !d.excluded || !isSimMode);
    // 현재 보기 모드에 맞는 share 사용
    const getShare = (row) => {
      if (isSimMode && row.simShare != null) return row.simShare;
      if (viewMode === 'combined') return row.combinedShare;
      if (viewMode === 'prev') return row.prevShare;
      return row.currentShare;
    };

    // 5단위 반올림 배분
    const raw = {};
    activeRows.forEach(r => { raw[r.size] = Math.round((getShare(r) * total) / 5) * 5; });

    // 총합 보정 → 가장 비중 큰 사이즈에서 조정
    const allocated = Object.values(raw).reduce((a, b) => a + b, 0);
    const diff = total - allocated;
    if (diff !== 0) {
      const maxRow = activeRows.reduce((a, b) => getShare(a) > getShare(b) ? a : b);
      raw[maxRow.size] = (raw[maxRow.size] || 0) + diff;
    }

    return raw;
  }, [totalOrderQty, chartData, isSimMode, viewMode]);

  // 입력 blur 시 5단위 보정
  const handleOrderBlur = () => {
    const val = Number(totalOrderQty);
    if (val > 0) setTotalOrderQty(String(Math.round(val / 5) * 5));
  };

  // Toggle size exclusion
  const toggleSize = (size) => {
    setExcludedSizes(prev => {
      const next = new Set(prev);
      if (next.has(size)) next.delete(size); else next.add(size);
      return next;
    });
  };

  // Get bar dataKey and color based on view mode
  const getBarConfig = () => {
    if (viewMode === 'prev') return { key: 'prevShare', color: '#94a3b8', label: '전년' };
    if (viewMode === 'compare') return null; // handled separately
    if (viewMode === 'combined') {
      if (isSimMode) return { key: 'simShare', color: '#60a5fa', label: '시뮬레이션' };
      return { key: 'combinedShare', color: '#7c3aed', label: '통합' };
    }
    if (isSimMode) return { key: 'simShare', color: '#60a5fa', label: '시뮬레이션' };
    return { key: 'currentShare', color: '#2563eb', label: '당해' };
  };

  const barConfig = getBarConfig();

  const filterLabels = { SEX_NM: '성별', CLASS2: '복종', CAT_NM: '카테고리', ITEM_NM: '아이템명' };

  return (
    <>
      <ColorMappingModal isOpen={showColorModal} onClose={() => setShowColorModal(false)} data={colorMapping} />
      <SizeDistributionModal
        isOpen={showSizeDistModal}
        onClose={() => setShowSizeDistModal(false)}
        orders={confirmedOrders}
        salesData={salesData}
        prevData={prevData}
        colorMapping={colorMapping}
        sizeOrder={sizeOrder}
      />

      {/* Lite 전용: 본인 사이즈 배분 리셋 */}
      <div className="flex justify-end mb-3">
        <ResetButton
          api={api}
          scope="size"
          label="Reset"
          confirmMessage="본인이 저장한 사이즈 배분(시뮬레이션·미러링) 결과를 삭제하고 운영팀 디폴트로 되돌립니다."
          onDone={() => window.location.reload()}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 lg:items-stretch">

        {/* Left Sidebar */}
        <div className="lg:col-span-1 flex flex-col gap-4">

          {/* View Mode Tabs — matches color range bar height on right */}
          <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
            {[
              { key: 'current', label: '당해' },
              { key: 'prev', label: '전년' },
              { key: 'compare', label: '비교' },
              { key: 'combined', label: '통합' },
            ].map(tab => (
              <button
                key={tab.key}
                onClick={() => { setViewMode(tab.key); if (tab.key === 'prev' || tab.key === 'compare') setIsSimMode(false); }}
                className={`flex-1 px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
                  viewMode === tab.key ? 'bg-white shadow text-blue-600' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Filters */}
          <div className="bg-white p-5 rounded-xl shadow-sm border border-gray-100 flex-1">
            <div className="flex items-center gap-2 mb-4 text-blue-700 font-semibold">
              <Filter className="w-5 h-5" />
              <span>조회 조건</span>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{filterLabels.SEX_NM}</label>
                <select value={selSex} onChange={e => handleSexChange(e.target.value)} className="w-full p-2 border border-gray-300 rounded-lg">
                  {sexOptions.map(o => <option key={o} value={o}>{o === 'All' ? '전체' : o}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{filterLabels.CLASS2}</label>
                <select value={selClass} onChange={e => handleClassChange(e.target.value)} className="w-full p-2 border border-gray-300 rounded-lg">
                  {classOptions.map(o => <option key={o} value={o}>{o === 'All' ? '전체' : o}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{filterLabels.CAT_NM}</label>
                <select value={selCat} onChange={e => handleCatChange(e.target.value)} className="w-full p-2 border border-gray-300 rounded-lg">
                  {catOptions.map(o => <option key={o} value={o}>{o === 'All' ? '전체' : o}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{filterLabels.ITEM_NM}</label>
                <select value={selItemNm} onChange={e => handleItemNmChange(e.target.value)} className="w-full p-2 border border-gray-300 rounded-lg">
                  {itemNmOptions.map(o => <option key={o} value={o}>{o === 'All' ? '전체' : o}</option>)}
                </select>
              </div>
            </div>
          </div>

        </div>

        {/* Right Top: Color Range Bar + Chart */}
        <div className="lg:col-span-3 flex flex-col gap-4">

          {/* Color Range Bar: Mapping Button + Dropdown + 사이즈 배분 */}
          <div className="flex items-center gap-3">
            {colorMapping && colorMapping.length > 0 && (
              <button
                onClick={() => setShowColorModal(true)}
                className="py-2 px-4 bg-slate-100 border border-slate-200 rounded-lg shadow-sm text-slate-600 text-sm font-semibold hover:bg-slate-200 transition-all flex items-center gap-2 shrink-0"
              >
                <List className="w-4 h-4 text-slate-500" />
                Color Range Table
              </button>
            )}
            <div className="relative flex items-center gap-2">
              <button
                onClick={() => setShowColorPicker(!showColorPicker)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white hover:bg-gray-50 flex items-center gap-2"
              >
                <span className="text-gray-600">{selColorRanges.size === 0 ? '전체 컬러' : `${selColorRanges.size}개 선택`}</span>
                <svg className={`w-4 h-4 text-gray-400 transition-transform ${showColorPicker ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
              </button>
              {/* Selected color dots preview */}
              {selColorRanges.size > 0 && (
                <div className="flex items-center gap-1">
                  {[...selColorRanges].map(range => (
                    <span key={range} title={range} className={`inline-block w-5 h-5 rounded-full shrink-0 ${colorDotStyle(range)}`} />
                  ))}
                </div>
              )}
              {/* Dropdown panel */}
              {showColorPicker && (
                <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 p-2 min-w-[180px]">
                  <button
                    onClick={() => { setSelColorRanges(new Set()); setShowColorPicker(false); }}
                    className={`w-full text-left px-3 py-1.5 rounded text-sm ${selColorRanges.size === 0 ? 'bg-gray-100 font-semibold text-gray-800' : 'text-gray-600 hover:bg-gray-50'}`}
                  >
                    전체 (초기화)
                  </button>
                  <div className="border-t border-gray-100 mt-1 pt-1">
                    {colorRangeOptions.filter(o => o !== 'All').map(range => {
                      const selected = selColorRanges.has(range);
                      return (
                        <button
                          key={range}
                          onClick={() => {
                            setSelColorRanges(prev => {
                              const next = new Set(prev);
                              if (next.has(range)) next.delete(range); else next.add(range);
                              return next;
                            });
                          }}
                          className={`w-full text-left px-3 py-1.5 rounded text-sm flex items-center gap-2 ${selected ? 'bg-indigo-50 text-indigo-700' : 'text-gray-600 hover:bg-gray-50'}`}
                        >
                          <span className={`inline-block w-4 h-4 rounded-full shrink-0 ${colorDotStyle(range)}`} />
                          <span className="flex-1">{range}</span>
                          {selected && <span className="text-indigo-500 text-xs font-bold">✓</span>}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
            {/* 사이즈 배분 버튼 (Step 4→5 연동) */}
            <div className="ml-auto flex items-center gap-2">
              <button
                onClick={handleOpenSizeDist}
                className="py-2 px-4 bg-slate-800 border border-slate-800 rounded-lg shadow-sm text-white text-sm font-semibold hover:bg-slate-700 transition-all flex items-center gap-2"
              >
                <Package className="w-4 h-4" />
                확정수량 사이즈배분
              </button>
              <button
                onClick={handleDirectExcelExport}
                className="p-2 bg-white border border-gray-300 rounded-lg shadow-sm text-gray-600 hover:bg-gray-50 hover:text-gray-800 transition-all"
                title="사이즈배분 Excel 다운로드"
              >
                <Download className="w-4 h-4" />
              </button>
              {sizeDistError && (
                <span className="text-xs text-red-500">{sizeDistError}</span>
              )}
            </div>
          </div>

          {/* Chart - stretches to match left sidebar height */}
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 relative flex-1 flex flex-col min-h-[350px]">
            <div className="flex justify-between items-start mb-4 shrink-0">
              <div>
                <h3 className="text-lg font-bold text-gray-800">
                  {isSimMode ? '제안 배분율 (Simulated)' : viewMode === 'compare' ? '당해 vs 전년 비교' : viewMode === 'combined' ? '2개년 통합 판매 비중' : '사이즈별 판매 비중'}
                </h3>
                <p className="text-sm text-gray-500">
                  {isSimMode
                    ? `제외: ${excludedSizes.size > 0 ? [...excludedSizes].join(', ') : '없음'}${mirrorPrev ? ' / 전년 미러링 ON' : ''}`
                    : viewMode === 'compare' ? '당해(파랑) vs 전년(회색) 배분율' : viewMode === 'combined' ? '당해 + 전년 합산' : `${viewMode === 'prev' ? '전년' : '당해'} 판매 실적`}
                </p>
              </div>
              {topSize && viewMode !== 'compare' && (
                <div className="text-right">
                  <span className="text-xs text-gray-500">최대 비중 사이즈</span>
                  <div className="font-bold text-blue-600 text-xl">{topSize.size} ({(topSize.share * 100).toFixed(1)}%)</div>
                </div>
              )}
            </div>

            <div className="flex-1">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData.filter(d => !d.excluded || !isSimMode)} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                  <XAxis dataKey="size" tick={{ fill: '#6b7280' }} axisLine={{ stroke: '#e5e7eb' }} />
                  <YAxis tickFormatter={v => `${(v * 100).toFixed(0)}%`} tick={{ fill: '#6b7280' }} axisLine={false} tickLine={false} />
                  <Tooltip
                    cursor={{ fill: '#f3f4f6' }}
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload;
                      return (
                        <div className="bg-white p-3 border border-blue-100 shadow-xl rounded-lg text-sm">
                          <p className="font-bold text-gray-800 mb-2">{d.size}</p>
                          {(viewMode === 'current' || viewMode === 'compare') && (
                            <>
                              <div className="flex justify-between gap-4">
                                <span className="text-gray-500">당해 비중:</span>
                                <span className="font-bold text-blue-600">{(d.currentShare * 100).toFixed(1)}%</span>
                              </div>
                              <div className="flex justify-between gap-4 mt-1">
                                <span className="text-gray-500">당해 판매:</span>
                                <span className="font-medium">{d.currentSale.toLocaleString()}</span>
                              </div>
                            </>
                          )}
                          {(viewMode === 'prev' || viewMode === 'compare') && (
                            <>
                              <div className="flex justify-between gap-4 mt-1">
                                <span className="text-gray-500">전년 비중:</span>
                                <span className="font-bold text-gray-600">{(d.prevShare * 100).toFixed(1)}%</span>
                              </div>
                              <div className="flex justify-between gap-4 mt-1">
                                <span className="text-gray-500">전년 판매:</span>
                                <span className="font-medium">{d.prevSale.toLocaleString()}</span>
                              </div>
                            </>
                          )}
                          {viewMode === 'combined' && (
                            <>
                              <div className="flex justify-between gap-4 mt-1">
                                <span className="text-gray-500">통합 비중:</span>
                                <span className="font-bold text-purple-600">{(d.combinedShare * 100).toFixed(1)}%</span>
                              </div>
                              <div className="flex justify-between gap-4 mt-1">
                                <span className="text-gray-500">통합 판매:</span>
                                <span className="font-medium">{d.combinedSale.toLocaleString()}</span>
                              </div>
                            </>
                          )}
                          {isSimMode && d.simShare != null && (
                            <div className="flex justify-between gap-4 mt-1 pt-1 border-t border-gray-100">
                              <span className="text-blue-500">시뮬레이션:</span>
                              <span className="font-bold text-blue-600">{(d.simShare * 100).toFixed(1)}%</span>
                            </div>
                          )}
                        </div>
                      );
                    }}
                  />
                  {viewMode === 'compare' ? (
                    <>
                      <Bar dataKey="currentShare" name="당해" fill="#2563eb" radius={[4, 4, 0, 0]}>
                        <LabelList dataKey="currentShare" position="top" formatter={v => v > 0 ? `${(v * 100).toFixed(1)}%` : ''} style={{ fill: '#2563eb', fontSize: '10px' }} />
                      </Bar>
                      <Bar dataKey="prevShare" name="전년" fill="#94a3b8" radius={[4, 4, 0, 0]}>
                        <LabelList dataKey="prevShare" position="top" formatter={v => v > 0 ? `${(v * 100).toFixed(1)}%` : ''} style={{ fill: '#94a3b8', fontSize: '10px' }} />
                      </Bar>
                      <Legend />
                    </>
                  ) : (
                    <Bar dataKey={barConfig.key} radius={[4, 4, 0, 0]}>
                      {chartData.filter(d => !d.excluded || !isSimMode).map((entry, index) => {
                        const highlightColor = viewMode === 'combined' ? '#5b21b6' : viewMode === 'prev' ? '#64748b' : '#2563eb';
                        return <Cell key={index} fill={entry.size === topSize?.size ? highlightColor : barConfig.color} />;
                      })}
                      <LabelList dataKey={barConfig.key} position="top" formatter={v => v > 0 ? `${(v * 100).toFixed(1)}%` : ''} style={{ fill: '#6b7280', fontSize: '11px' }} />
                    </Bar>
                  )}
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-gray-400">
                선택된 조건에 해당하는 데이터가 없습니다.
              </div>
            )}
            </div>
          </div>

        </div>

        {/* Row 2: Simulation (left) + Table (right) */}
        <div className="lg:col-span-1">
          {/* Simulation */}
          <div className={`p-5 rounded-xl shadow-sm border transition-all ${isSimMode ? 'bg-indigo-50 border-indigo-200' : 'bg-white border-gray-100'}`}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2 font-semibold text-gray-800">
                <Calculator className="w-5 h-5" />
                <span>발주 시뮬레이션</span>
              </div>
              <button
                onClick={() => { setIsSimMode(!isSimMode); if (!isSimMode) setViewMode('current'); }}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${isSimMode ? 'bg-indigo-600' : 'bg-gray-200'}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${isSimMode ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>

            {isSimMode && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">포함 사이즈 선택</label>
                  <div className="flex gap-2 overflow-x-auto">
                    {sizeOrder.map(size => {
                      const exists = chartData.some(d => d.size === size);
                      if (!exists) return null;
                      const excluded = excludedSizes.has(size);
                      return (
                        <button
                          key={size}
                          onClick={() => toggleSize(size)}
                          className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${
                            excluded
                              ? 'bg-gray-100 text-gray-400 border-gray-200 line-through'
                              : 'bg-indigo-100 text-indigo-700 border-indigo-200'
                          }`}
                        >
                          {size}
                        </button>
                      );
                    })}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">* 제외 사이즈 비중 → 나머지로 100% 재배분</p>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium text-gray-700">전년 미러링</label>
                    <p className="text-xs text-gray-500">당해 판매 0인 사이즈에 전년 비중 적용</p>
                  </div>
                  <button
                    onClick={() => setMirrorPrev(!mirrorPrev)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${mirrorPrev ? 'bg-indigo-600' : 'bg-gray-200'}`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${mirrorPrev ? 'translate-x-6' : 'translate-x-1'}`} />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-3">
          {/* Table */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="p-4 border-b border-gray-100 bg-gray-50 flex justify-between items-center">
              <h3 className="font-semibold text-gray-800">
                {isSimMode ? '발주 제안 가이드 (Proposal)' : '상세 실적 데이터'}
              </h3>
              <div className="flex items-center gap-2">
                {isSimMode && <span className="bg-indigo-100 text-indigo-700 text-xs px-2 py-1 rounded font-medium">Simulation Active</span>}
                <label className="text-sm text-gray-500">총 발주수량</label>
                <input
                  type="number"
                  value={totalOrderQty}
                  onChange={e => setTotalOrderQty(e.target.value)}
                  onBlur={handleOrderBlur}
                  placeholder="예: 10000"
                  className="w-32 px-3 py-1.5 border border-gray-300 rounded-lg text-sm text-right focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400"
                />
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-gray-50 text-gray-500 font-medium">
                  <tr>
                    <th className="px-6 py-3">사이즈</th>
                    {(viewMode === 'current' || viewMode === 'compare') && (
                      <>
                        <th className="px-6 py-3 text-right">당해 발주</th>
                        <th className="px-6 py-3 text-right">당해 판매</th>
                        <th className="px-6 py-3 text-right">당해 비중</th>
                      </>
                    )}
                    {(viewMode === 'prev' || viewMode === 'compare') && (
                      <>
                        <th className="px-6 py-3 text-right">전년 발주</th>
                        <th className="px-6 py-3 text-right">전년 판매</th>
                        <th className="px-6 py-3 text-right">전년 비중</th>
                      </>
                    )}
                    {viewMode === 'combined' && (
                      <>
                        <th className="px-6 py-3 text-right">통합 발주</th>
                        <th className="px-6 py-3 text-right">통합 판매</th>
                        <th className="px-6 py-3 text-right">통합 비중</th>
                      </>
                    )}
                    {isSimMode && <th className="px-6 py-3 text-right">시뮬 배분율</th>}
                    <th className="px-6 py-3 text-right">배분 수량</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {chartData.map(row => {
                    if (isSimMode && row.excluded) return null;
                    const activeShare = isSimMode ? (row.simShare || 0)
                      : viewMode === 'combined' ? row.combinedShare
                      : viewMode === 'prev' ? row.prevShare : row.currentShare;
                    const highlight = activeShare >= 0.15;
                    return (
                      <tr key={row.size} className={`transition-colors ${highlight ? 'bg-blue-50/30' : 'hover:bg-gray-50'}`}>
                        <td className="px-6 py-3 font-medium text-gray-900">{row.size}</td>
                        {(viewMode === 'current' || viewMode === 'compare') && (
                          <>
                            <td className="px-6 py-3 text-right text-gray-700">{row.currentOrder.toLocaleString()}</td>
                            <td className="px-6 py-3 text-right text-gray-900 font-medium">{row.currentSale.toLocaleString()}</td>
                            <td className="px-6 py-3 text-right">
                              <span className={`px-2 py-1 rounded-full font-medium ${row.currentShare >= 0.15 ? 'bg-blue-100 text-blue-700' : 'text-gray-600'}`}>
                                {(row.currentShare * 100).toFixed(1)}%
                              </span>
                            </td>
                          </>
                        )}
                        {(viewMode === 'prev' || viewMode === 'compare') && (
                          <>
                            <td className="px-6 py-3 text-right text-gray-700">{row.prevOrder.toLocaleString()}</td>
                            <td className="px-6 py-3 text-right text-gray-900 font-medium">{row.prevSale.toLocaleString()}</td>
                            <td className="px-6 py-3 text-right">
                              <span className={`px-2 py-1 rounded-full font-medium ${row.prevShare >= 0.15 ? 'bg-gray-200 text-gray-700' : 'text-gray-600'}`}>
                                {(row.prevShare * 100).toFixed(1)}%
                              </span>
                            </td>
                          </>
                        )}
                        {viewMode === 'combined' && (
                          <>
                            <td className="px-6 py-3 text-right text-gray-700">{row.combinedOrder.toLocaleString()}</td>
                            <td className="px-6 py-3 text-right text-gray-900 font-medium">{row.combinedSale.toLocaleString()}</td>
                            <td className="px-6 py-3 text-right">
                              <span className={`px-2 py-1 rounded-full font-medium ${row.combinedShare >= 0.15 ? 'bg-purple-100 text-purple-700' : 'text-gray-600'}`}>
                                {(row.combinedShare * 100).toFixed(1)}%
                              </span>
                            </td>
                          </>
                        )}
                        {isSimMode && (
                          <td className="px-6 py-3 text-right">
                            <span className="px-2 py-1 rounded-full font-medium bg-blue-100 text-blue-700">
                              {((row.simShare || 0) * 100).toFixed(1)}%
                            </span>
                          </td>
                        )}
                        <td className="px-6 py-3 text-right font-medium text-indigo-700">
                          {allocatedOrders[row.size] != null ? allocatedOrders[row.size].toLocaleString() : '-'}
                        </td>
                      </tr>
                    );
                  })}
                  {chartData.length === 0 && (
                    <tr><td colSpan="8" className="px-6 py-8 text-center text-gray-400">데이터가 없습니다.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

      </div>
    </>
  );
}
