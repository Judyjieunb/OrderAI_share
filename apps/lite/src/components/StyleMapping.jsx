import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext.jsx';
import { useBrandSeason } from '../contexts/BrandSeasonContext.jsx';
import { createApiClient } from '../service/apiClient.js';
import { Loader2, CheckCircle2, AlertTriangle, Upload, Download, X, FileSpreadsheet, SlidersHorizontal } from 'lucide-react';
import { publicUrl, apiUrl } from '../utils/api.js';
import ResetButton from './common/ResetButton.jsx';
import { CHANGED_CELL_CLASS } from '../utils/highlight.js';

export default function StyleMapping() {
  const { user } = useAuth();
  const { brand, season } = useBrandSeason();
  const api = useMemo(
    () => createApiClient(user?.email, brand, season, user?.role),
    [user?.email, brand, season],
  );
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selections, setSelections] = useState({});     // { new_part_cd: ref_part_cd | 'MANUAL' }
  const [manualQty, setManualQty] = useState({});       // { new_part_cd: number }
  const [manualRefSearch, setManualRefSearch] = useState({});  // { new_part_cd: PART_CD 입력 중 }
  const [manualRefResult, setManualRefResult] = useState({});  // { new_part_cd: ref-style 조회 결과 }
  const [manualRefError, setManualRefError] = useState({});    // { new_part_cd: 에러 메시지 }
  const [manualRefLoading, setManualRefLoading] = useState({});// { new_part_cd: bool }
  const [classFilter, setClassFilter] = useState('all');
  const [itemFilter, setItemFilter] = useState('all');
  const [showManualOnly, setShowManualOnly] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [goListApplied, setGoListApplied] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  // Template 다운로드
  const handleDownloadTemplate = useCallback(async () => {
    const XLSX = await import('xlsx');
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet([['CLASS2', 'ITEM', 'STYLE_CD', 'COLOR_CD', 'SIZE_RANGE']]);
    ws['!cols'] = [{ wch: 12 }, { wch: 10 }, { wch: 16 }, { wch: 12 }, { wch: 20 }];
    XLSX.utils.book_append_sheet(wb, ws, 'GO List');
    XLSX.writeFile(wb, 'go_list_template.xlsx');
  }, []);

  // GO list 업로드
  const handleUploadFile = useCallback(async (file) => {
    if (!file || !file.name.match(/\.xlsx?$/i)) {
      setUploadResult({ success: false, message: '.xlsx 파일만 업로드 가능합니다.' });
      return;
    }
    setUploading(true);
    setUploadResult(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.postForm('/api/go-list', formData);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `서버 오류 (${res.status})`);
      }
      const result = await res.json();
      setUploadResult({ success: true, data: result });
      setGoListApplied(true);
      setShowUploadModal(false);
      // 데이터 리로드
      loadData();
    } catch (err) {
      setUploadResult({ success: false, message: err.message });
    } finally {
      setUploading(false);
    }
  }, []);

  // GO list 리셋
  const handleResetGoList = useCallback(async () => {
    // 파이프라인 원본으로 복원 (step4_integration 재실행은 무거우므로 단순 플래그 리셋)
    setGoListApplied(false);
    setUploadResult(null);
    // 원본 style_mapping_data.json 재생성 필요 → 유저에게 안내
    alert('GO list가 해제되었습니다. 전체 목록을 보려면 파이프라인을 다시 실행해주세요 (run_all.py).');
  }, []);

  // 드래그앤드롭 핸들러
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUploadFile(file);
  }, [handleUploadFile]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => setDragOver(false), []);

  // 데이터 로딩 함수
  const loadData = useCallback(() => {
    setLoading(true);
    api.fetchFile('style_mapping_data.json')
      .then(json => {
        if (!json || !json.metadata?.go_list) {
          // GO list 미적용 → 데이터 표시하지 않음
          setData(null);
          setLoading(false);
          return;
        }
        setData(json);
        const defaults = {};
        for (const style of json.styles) {
          if (style.references.length > 0) {
            const validRef = style.references.find(r => r.AI발주량 > 0);
            if (validRef) {
              defaults[style.new_part_cd] = validRef.part_cd;
            }
          }
        }
        setSelections(defaults);
        setLoading(false);
      })
      .catch(() => {
        setData(null);
        setLoading(false);
      });
  }, [api]);

  useEffect(() => { loadData(); }, [loadData]);

  // GO list 적용 상태 확인
  useEffect(() => {
    if (data?.metadata?.go_list) setGoListApplied(true);
  }, [data]);

  // Class 목록 (Inner/Outer/Bottom)
  const classList = useMemo(() => {
    if (!data) return [];
    const set = new Set(data.styles.map(s => s.go_class2 || s.class2 || '').filter(Boolean));
    return [...set].sort();
  }, [data]);

  // Item 목록 (classFilter 연동)
  const itemList = useMemo(() => {
    if (!data) return [];
    let list = data.styles;
    if (classFilter !== 'all') list = list.filter(s => (s.go_class2 || s.class2 || '') === classFilter);
    const set = new Set(list.map(s => s.go_item || s.new_item_nm || '').filter(Boolean));
    return [...set].sort();
  }, [data, classFilter]);

  // 필터링된 스타일 (건수 표시용: 수동입력 필터 제외)
  const baseFilteredStyles = useMemo(() => {
    if (!data) return [];
    let list = data.styles;
    if (classFilter !== 'all') list = list.filter(s => (s.go_class2 || s.class2 || '') === classFilter);
    if (itemFilter !== 'all') list = list.filter(s => (s.go_item || s.new_item_nm || '') === itemFilter);
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toUpperCase();
      list = list.filter(s => s.new_part_cd.toUpperCase().includes(q));
    }
    return list;
  }, [data, classFilter, itemFilter, searchQuery]);

  // 테이블 표시용 (수동입력 필터 포함)
  const filteredStyles = useMemo(() => {
    let list = baseFilteredStyles;
    if (showManualOnly) list = list.filter(s => !selections[s.new_part_cd]);
    return list;
  }, [baseFilteredStyles, showManualOnly, selections]);

  // 수동입력 대상: refs가 없거나, 모든 ref의 AI발주량이 0인 스타일, 또는 직접입력(MANUAL) 라디오 선택
  const manualStyleCount = useMemo(() => {
    if (!data) return 0;
    return data.styles.filter(s => {
      const sel = selections[s.new_part_cd];
      return !sel || sel === 'MANUAL';
    }).length;
  }, [data, selections]);

  // 확정 진행률: Top 1~3 선택 + 직접입력(조회 성공 OR 수량 입력) + 매핑 불가 수량 입력
  const totalStyles = data?.metadata.total_styles || 0;
  const matchedSelections = Object.entries(selections).filter(([, v]) => v && v !== 'MANUAL').length;
  const manualEntries = data?.styles
    ? data.styles.filter(s => {
        const sel = selections[s.new_part_cd];
        const qty = manualQty[s.new_part_cd] || 0;
        if (sel === 'MANUAL') return manualRefResult[s.new_part_cd]?.found || qty > 0;
        if (!sel && s.references.length === 0) return qty > 0;
        return false;
      }).length
    : 0;
  const confirmedCount = matchedSelections + manualEntries;

  // 선택 핸들러
  const handleSelect = (newPartCd, refPartCd) => {
    setSelections(prev => ({ ...prev, [newPartCd]: refPartCd }));
    setSaveResult(null);
  };

  // 수동 발주량 핸들러
  const handleManualQty = (newPartCd, value) => {
    const qty = parseInt(value, 10);
    setManualQty(prev => ({ ...prev, [newPartCd]: isNaN(qty) ? 0 : qty }));
    setSaveResult(null);
  };

  // 직접 입력 PART_CD 조회 (과거 3시즌 ref lookup)
  const handleRefLookup = async (newPartCd) => {
    const partCd = (manualRefSearch[newPartCd] || '').trim().toUpperCase();
    if (!partCd) return;
    if (partCd === newPartCd.toUpperCase()) {
      setManualRefError(prev => ({ ...prev, [newPartCd]: '자기 자신을 ref로 매핑할 수 없습니다.' }));
      setManualRefResult(prev => ({ ...prev, [newPartCd]: null }));
      return;
    }
    setManualRefLoading(prev => ({ ...prev, [newPartCd]: true }));
    setManualRefError(prev => ({ ...prev, [newPartCd]: null }));
    try {
      const res = await api.get(`/api/ref-style?part_cd=${encodeURIComponent(partCd)}`);
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `조회 실패 (${res.status})`);
      }
      const result = await res.json();
      setManualRefResult(prev => ({ ...prev, [newPartCd]: result }));
      setManualQty(prev => ({ ...prev, [newPartCd]: result.AI발주량 || 0 }));
      setSelections(prev => ({ ...prev, [newPartCd]: 'MANUAL' }));
      setSaveResult(null);
    } catch (err) {
      setManualRefError(prev => ({ ...prev, [newPartCd]: err.message || '조회 실패' }));
      setManualRefResult(prev => ({ ...prev, [newPartCd]: null }));
    } finally {
      setManualRefLoading(prev => ({ ...prev, [newPartCd]: false }));
    }
  };

  // 확정 저장
  const handleConfirm = async () => {
    setSaving(true);
    setSaveResult(null);

    const mappings = [];

    for (const style of data.styles) {
      const npc = style.new_part_cd;
      const sel = selections[npc];
      const qty = manualQty[npc] || 0;
      const refResult = manualRefResult[npc];
      const baseItem = {
        new_part_cd: npc,
        new_item_nm: style.new_item_nm,
        new_prdt_nm: style.new_prdt_nm || '',
        new_class2: style.new_class2,
        class2: style.class2 || '',
      };

      // 우선순위: 사용자 직접입력(manualRefResult) > 사용자 라디오 선택 > baseline default
      // selections state는 GO list 재업로드로 reset될 수 있으나 manualRefResult/manualQty는 유지됨.
      // 따라서 사용자 의도는 manualRef를 가장 신뢰 가능한 신호로 사용.
      let effectiveSel = sel;
      if (refResult?.found) {
        effectiveSel = 'MANUAL';
      } else if (!effectiveSel && style.references && style.references.length > 0) {
        const validRef = style.references.find(r => r.AI발주량 > 0);
        if (validRef) effectiveSel = validRef.part_cd;
      }

      // Case 1: Top 1~3 라디오 선택 (사용자 명시 OR baseline default)
      if (effectiveSel && effectiveSel !== 'MANUAL' && style.references.length > 0) {
        const ref = style.references.find(r => r.part_cd === effectiveSel);
        const item = {
          ...baseItem,
          selected_ref_part_cd: effectiveSel,
          selected_ref_score: ref ? ref.score : 0,
        };
        if (style.go_size_range) item.size_range = style.go_size_range;
        mappings.push(item);
      }
      // Case 2: 직접입력 라디오 + PART_CD 조회 성공
      else if (effectiveSel === 'MANUAL' && refResult?.found) {
        const item = {
          ...baseItem,
          selected_ref_part_cd: refResult.part_cd,
          selected_ref_score: 0,
        };
        // 운영자가 자동 채움 수량을 수정한 경우만 manual_order_qty 전달 (확정 우선)
        if (qty > 0 && qty !== (refResult.AI발주량 || 0)) {
          item.manual_order_qty = qty;
        }
        if (style.go_size_range) item.size_range = style.go_size_range;
        mappings.push(item);
      }
      // Case 3: 직접입력 라디오 + 수량만 입력 (조회 없음)
      else if (effectiveSel === 'MANUAL' && qty > 0) {
        const item = { ...baseItem, manual_order_qty: qty };
        if (style.go_size_range) item.size_range = style.go_size_range;
        mappings.push(item);
      }
      // Case 4: 매핑 불가 + 수량 입력 (기존 흐름, 라디오 없음)
      else if (!effectiveSel && style.references.length === 0 && qty > 0) {
        const item = { ...baseItem, manual_order_qty: qty };
        if (style.go_size_range) item.size_range = style.go_size_range;
        mappings.push(item);
      }
    }

    try {
      const res = await api.post('/api/confirmed-mapping', { season: data.metadata.new_season, mappings });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `서버 오류 (${res.status})`);
      }
      const result = await res.json();
      setSaveResult({ success: true, data: result });
    } catch (err) {
      setSaveResult({ success: false, message: err.message });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96 text-gray-400">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        <span>맵핑 데이터 로딩 중...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-gray-500 gap-3">
        <AlertTriangle className="w-8 h-8 text-amber-400" />
        <p className="text-sm">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FileSpreadsheet className="w-5 h-5 text-gray-400" />
            <span className="text-sm text-gray-700 font-medium">GO List</span>
            <span className="text-xs text-gray-400">진행할 스타일 목록을 업로드하세요</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleDownloadTemplate}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <Download className="w-4 h-4" />
              Template
            </button>
            <button
              onClick={() => setShowUploadModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
            >
              <Upload className="w-4 h-4" /> Upload
            </button>
          </div>
        </div>
        <div className="flex flex-col items-center justify-center h-80 text-gray-400 gap-3">
          <Upload className="w-10 h-10 text-gray-300" />
          <p className="text-sm font-medium text-gray-500">진행할 스타일/컬러 구성 및 사이즈레인지를 업로드하세요.</p>
          <p className="text-xs text-gray-400">.xlsx 파일 (CLASS2, ITEM, STYLE_CD, COLOR_CD 컬럼 필요)</p>
        </div>
        {showUploadModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
            <div className="bg-white rounded-2xl shadow-xl p-6 w-[480px] relative">
              <button onClick={() => { setShowUploadModal(false); setUploadResult(null); }} className="absolute top-3 right-3 text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
              <h3 className="text-lg font-semibold mb-4">GO List Upload</h3>
              <div
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${dragOver ? 'border-indigo-400 bg-indigo-50' : 'border-gray-200 hover:border-gray-300'}`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => { const input = document.createElement('input'); input.type = 'file'; input.accept = '.xlsx,.xls'; input.onchange = (e) => handleUploadFile(e.target.files[0]); input.click(); }}
              >
                <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                <p className="text-sm text-gray-600">파일을 드래그하거나 클릭하여 선택</p>
                <p className="text-xs text-gray-400 mt-1">.xlsx 파일 (CLASS2, ITEM, STYLE_CD, COLOR_CD)</p>
              </div>
              {uploading && <div className="flex items-center justify-center mt-4 text-sm text-gray-500"><Loader2 className="w-4 h-4 animate-spin mr-2" />업로드 중...</div>}
              {uploadResult && !uploadResult.success && <p className="mt-3 text-sm text-red-500 flex items-center gap-1"><AlertTriangle className="w-4 h-4" />{uploadResult.message}</p>}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* GO list 툴바 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileSpreadsheet className="w-5 h-5 text-gray-400" />
          <span className="text-sm text-gray-700 font-medium">GO List</span>
          {goListApplied ? (
            <span className="flex items-center gap-2 text-sm">
              <span className="flex items-center gap-1 px-2.5 py-1 bg-green-50 text-green-700 rounded-full text-xs font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" />
                적용됨: {data?.metadata?.go_total_styles || data?.metadata?.total_styles}개 스타일 업로드
                {data?.metadata?.go_unmatched_styles > 0 && (
                  <span className="text-amber-600 ml-1">
                    (유사스타일 매핑 불가 {data.metadata.go_unmatched_styles}개)
                  </span>
                )}
              </span>
              <button
                onClick={handleResetGoList}
                className="text-xs text-gray-400 hover:text-red-500 transition-colors"
                title="GO list 해제"
              >
                <X className="w-4 h-4" />
              </button>
            </span>
          ) : (
            <span className="text-xs text-gray-400">진행할 스타일 목록을 업로드하세요</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDownloadTemplate}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <Download className="w-4 h-4" />
            Template
          </button>
          <button
            onClick={() => setShowUploadModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white bg-slate-800 rounded-lg hover:bg-slate-700 transition-colors"
          >
            <Upload className="w-4 h-4" />
            Upload
          </button>
          {/* Lite 전용: GO list + 매핑 + 발주 + 사이즈 cascade 삭제 (사용자가 GO list부터 새로 시작) */}
          <ResetButton
            api={api}
            scope="mapping"
            label="Reset"
            confirmMessage="GO list, 매핑, 발주 추천, 사이즈 배분을 모두 삭제하고 처음부터 다시 시작합니다. 계속하시겠습니까?"
            onDone={() => window.location.reload()}
          />
        </div>
      </div>

      {/* 업로드 모달 */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl w-[480px] p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">GO List Upload</h3>
              <button onClick={() => { setShowUploadModal(false); setUploadResult(null); }} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
                dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls"
                className="hidden"
                onChange={e => { if (e.target.files[0]) handleUploadFile(e.target.files[0]); }}
              />
              {uploading ? (
                <div className="flex flex-col items-center gap-2">
                  <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                  <span className="text-sm text-gray-500">업로드 중...</span>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <Upload className="w-8 h-8 text-gray-300" />
                  <span className="text-sm text-gray-600">파일을 드래그하거나 클릭하여 선택</span>
                  <span className="text-xs text-gray-400">.xlsx 파일 (CLASS2, ITEM, STYLE_CD, COLOR_CD)</span>
                </div>
              )}
            </div>
            {uploadResult && !uploadResult.success && (
              <div className="mt-3 flex items-center gap-2 text-sm text-red-500">
                <AlertTriangle className="w-4 h-4" />
                {uploadResult.message}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 필터 + 액션 바 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <SlidersHorizontal className="w-4 h-4 text-gray-400" />
          <select
            value={classFilter}
            onChange={e => { setClassFilter(e.target.value); setItemFilter('all'); }}
            className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">전체 Class</option>
            {classList.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select
            value={itemFilter}
            onChange={e => setItemFilter(e.target.value)}
            className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">전체 Item</option>
            {itemList.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="품번 검색"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 w-36 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-300"
          />
          <span className="text-xs text-gray-400 ml-1">
            {baseFilteredStyles.length}건
          </span>
          <span className="text-xs text-gray-400">·</span>
          <span className="text-xs text-gray-400">
            매칭 <strong className="text-green-600">{baseFilteredStyles.filter(s => selections[s.new_part_cd]).length}</strong>
          </span>
          <span className="text-xs text-gray-400">·</span>
          <button
            onClick={() => setShowManualOnly(prev => !prev)}
            className={`text-xs rounded px-1.5 py-0.5 transition-colors ${
              showManualOnly ? 'bg-amber-100 text-amber-700 ring-1 ring-amber-300' : 'text-gray-400 hover:bg-amber-50'
            }`}
          >
            수동입력 <strong className="text-amber-500">{baseFilteredStyles.filter(s => !selections[s.new_part_cd]).length}</strong>
          </button>
        </div>
        <div className="flex items-center gap-3">
          {saveResult && saveResult.success && (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <CheckCircle2 className="w-3.5 h-3.5" />
              총 {saveResult.data.total_recommendation_qty?.toLocaleString()}장 — Step 4에서 확인
            </span>
          )}
          {saveResult && !saveResult.success && (
            <span className="flex items-center gap-1 text-xs text-red-500">
              <AlertTriangle className="w-3.5 h-3.5" />
              {saveResult.message}
            </span>
          )}
          <span className="text-sm text-gray-500">
            <strong className="text-blue-600">{confirmedCount}</strong>/{totalStyles} 확정
          </span>
          <button
            onClick={handleConfirm}
            disabled={saving || confirmedCount === 0}
            className="flex items-center gap-2 px-4 py-1.5 bg-slate-800 text-white rounded-lg text-sm font-medium hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <CheckCircle2 className="w-4 h-4" />
            )}
            스타일확정
          </button>
        </div>
      </div>

      {/* 테이블 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="max-h-[calc(100vh-340px)] overflow-y-auto">
          <table className="w-full text-sm table-fixed">
            <thead className="bg-gray-50 border-b border-gray-200 sticky top-0 z-10">
              <tr>
                <th className="w-[3%] px-2 py-3 text-center text-xs font-semibold text-gray-500">#</th>
                <th className="w-[9%] px-3 py-3 text-left text-xs font-semibold text-gray-500">클래스</th>
                <th className="w-[6%] px-3 py-3 text-left text-xs font-semibold text-gray-500">아이템</th>
                <th className="w-[10%] px-3 py-3 text-left text-xs font-semibold text-gray-500">신규 품번</th>
                <th className="w-[4%] px-2 py-3 text-center text-xs font-semibold text-gray-500">선택</th>
                <th className="w-[10%] px-3 py-3 text-left text-xs font-semibold text-gray-500">유사 품번</th>
                <th className="w-[17%] px-3 py-3 text-left text-xs font-semibold text-gray-500">품명</th>
                <th className="w-[7%] px-3 py-ㅇ3 text-center text-xs font-semibold text-gray-500">ML유사도</th>
                <th className="w-[7%] px-3 py-3 text-right text-xs font-semibold text-gray-500">판매율</th>
                <th className="w-[9%] px-3 py-3 text-right text-xs font-semibold text-gray-500">총판매</th>
                <th className="w-[9%] px-3 py-3 text-right text-xs font-semibold text-gray-500">총입고</th>
                <th className="w-[9%] px-3 py-3 text-right text-xs font-semibold text-gray-500">AI발주량</th>
              </tr>
            </thead>
            <tbody>
              {filteredStyles.map((style, idx) => {
                const refs = style.references;
                const npc = style.new_part_cd;
                const sel = selections[npc];
                const hasRefs = refs.length > 0;
                const rowCount = hasRefs ? refs.length + 1 : 1;
                const lookupResult = manualRefResult[npc];
                const lookupError = manualRefError[npc];
                const lookupLoading = manualRefLoading[npc];
                const isMANUAL = sel === 'MANUAL';

                const manualRow = (
                  <tr
                    key={`${npc}-MANUAL`}
                    className={`border-b border-gray-200 transition-colors ${
                      isMANUAL ? 'bg-amber-100/70' : hasRefs ? 'bg-amber-50/30 hover:bg-amber-50/60' : 'bg-amber-50/40'
                    }`}
                  >
                    {!hasRefs && (
                      <>
                        <td className="px-2 py-2.5 text-center text-xs text-gray-400 border-r border-gray-100">{idx + 1}</td>
                        <td className="px-3 py-2.5 text-xs text-gray-500 break-words border-r border-gray-100">{style.go_class2 || style.class2 || style.new_class2}</td>
                        <td className="px-3 py-2.5 text-xs text-gray-700 break-words border-r border-gray-100">{style.new_item_nm}</td>
                        <td className="px-3 py-2.5 text-xs font-mono text-gray-800 break-words border-r border-gray-100">{npc}</td>
                      </>
                    )}
                    <td className="px-2 py-2 text-center">
                      {hasRefs ? (
                        <input
                          type="radio"
                          name={`ref-${npc}`}
                          checked={isMANUAL}
                          onChange={() => handleSelect(npc, 'MANUAL')}
                          className="w-3.5 h-3.5 text-amber-600 cursor-pointer"
                        />
                      ) : (
                        <span className="text-xs text-gray-300">-</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1">
                        <input
                          type="text"
                          placeholder="품번"
                          value={manualRefSearch[npc] || ''}
                          onChange={e => setManualRefSearch(prev => ({ ...prev, [npc]: e.target.value.toUpperCase() }))}
                          onKeyDown={e => { if (e.key === 'Enter') handleRefLookup(npc); }}
                          className="w-20 text-xs font-mono border border-amber-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-amber-400 bg-white"
                        />
                        <button
                          onClick={() => handleRefLookup(npc)}
                          disabled={lookupLoading || !manualRefSearch[npc]}
                          className="px-3 py-1 text-xs bg-amber-200 hover:bg-amber-300 disabled:bg-gray-100 disabled:text-gray-400 rounded font-medium whitespace-nowrap"
                        >
                          {lookupLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : '조회'}
                        </button>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-xs break-words">
                      {lookupError ? (
                        <span className="text-red-500">{lookupError}</span>
                      ) : (
                        <span className="text-gray-600">{lookupResult?.prdt_nm || lookupResult?.item_nm || (hasRefs ? '직접 입력' : '매칭 불가 — 예상 발주량 직접 입력')}</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-amber-200 text-amber-700">수동</span>
                    </td>
                    <td className="px-3 py-2 text-right text-xs text-gray-700">
                      {lookupResult?.판매율 != null ? `${Number(lookupResult.판매율).toFixed(1)}%` : '-'}
                    </td>
                    <td className="px-3 py-2 text-right text-xs text-gray-700">
                      {lookupResult?.총판매 != null ? Number(lookupResult.총판매).toLocaleString() : '-'}
                    </td>
                    <td className="px-3 py-2 text-right text-xs text-gray-700">
                      {lookupResult?.총입고 != null ? Number(lookupResult.총입고).toLocaleString() : '-'}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <input
                        type="number"
                        min="0"
                        step="10"
                        placeholder="수량"
                        value={manualQty[npc] || ''}
                        onChange={e => handleManualQty(npc, e.target.value)}
                        className="w-24 text-xs text-right border border-amber-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-amber-400 bg-white"
                      />
                    </td>
                  </tr>
                );

                if (!hasRefs) return manualRow;

                return (
                  <React.Fragment key={npc}>
                    {refs.map((ref, refIdx) => {
                      const isSelected = sel === ref.part_cd;
                      const isFirst = refIdx === 0;
                      return (
                        <tr
                          key={`${npc}-${ref.rank}`}
                          className={`${isSelected ? 'bg-blue-50/70' : 'hover:bg-gray-50/50'} transition-colors`}
                        >
                          {isFirst && (
                            <>
                              <td rowSpan={rowCount} className="px-2 py-2.5 text-center text-xs text-gray-400 align-top border-r border-gray-100">
                                {idx + 1}
                              </td>
                              <td rowSpan={rowCount} className="px-3 py-2.5 text-xs text-gray-500 align-top border-r border-gray-100 break-words">
                                {style.go_class2 || style.class2 || style.new_class2}
                              </td>
                              <td rowSpan={rowCount} className="px-3 py-2.5 text-xs text-gray-700 align-top border-r border-gray-100 break-words">
                                {style.new_item_nm}
                              </td>
                              <td rowSpan={rowCount} className="px-3 py-2.5 text-xs font-mono text-gray-800 align-top border-r border-gray-100 break-words">
                                {npc}
                              </td>
                            </>
                          )}

                          <td className="px-2 py-2 text-center">
                            <input
                              type="radio"
                              name={`ref-${npc}`}
                              checked={isSelected}
                              onChange={() => handleSelect(npc, ref.part_cd)}
                              className="w-3.5 h-3.5 text-blue-600 cursor-pointer"
                            />
                          </td>
                          <td className="px-3 py-2 text-xs font-mono text-gray-700">{ref.part_cd}</td>
                          <td className="px-3 py-2 text-xs text-gray-600">{ref.prdt_nm || style.new_prdt_nm || ref.item_nm}</td>
                          <td className="px-3 py-2 text-center">
                            <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                              ref.rank === 1 ? 'bg-red-200 text-red-800' :
                              ref.rank === 2 ? 'bg-red-100 text-red-600' :
                              'bg-red-50 text-red-500'
                            }`}>
                              Top{ref.rank}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right text-xs text-gray-700">{ref.판매율.toFixed(1)}%</td>
                          <td className="px-3 py-2 text-right text-xs text-gray-700">{ref.총판매.toLocaleString()}</td>
                          <td className="px-3 py-2 text-right text-xs text-gray-700">{ref.총입고.toLocaleString()}</td>
                          <td className="px-3 py-2 text-right text-xs font-medium text-gray-800">{ref.AI발주량.toLocaleString()}</td>
                        </tr>
                      );
                    })}
                    {manualRow}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
