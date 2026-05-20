import { useState } from 'react'
import { RotateCcw, X } from 'lucide-react'

/**
 * Lite Reset 버튼 — 본인 사물함을 비우고 운영팀 baseline으로 복귀.
 *
 * Props:
 *   - api: createApiClient() 결과물 (resetScope 사용)
 *   - scope: 'mapping' | 'orders' | 'size' | 'go' | 'all'
 *   - label: 버튼 라벨 (선택, 기본 '리셋')
 *   - confirmMessage: 확인 모달 본문 (선택)
 *   - onDone: 리셋 성공 후 콜백 (재조회 트리거 등)
 *   - className: 추가 클래스
 */
export default function ResetButton({
  api,
  scope = 'all',
  label = '리셋',
  confirmMessage,
  onDone,
  className = '',
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const defaultMsg =
    scope === 'all'
      ? '본인 사물함의 모든 변경 내역을 삭제하고 운영팀 디폴트로 되돌립니다. 계속하시겠어요?'
      : `본인 사물함의 [${scope}] 변경 내역을 삭제하고 운영팀 디폴트로 되돌립니다. 계속하시겠어요?`

  async function handleReset() {
    if (!api?.resetScope) {
      alert('API 클라이언트가 준비되지 않았습니다.')
      return
    }
    setBusy(true)
    try {
      const res = await api.resetScope(scope)
      if (!res.ok) {
        const msg = await res.text().catch(() => '')
        alert(`리셋 실패 (${res.status}): ${msg || '알 수 없는 오류'}`)
        return
      }
      setOpen(false)
      onDone?.()
    } catch (e) {
      alert(`리셋 실패: ${e.message || e}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded border border-slate-300 bg-white text-slate-600 hover:bg-slate-50 hover:border-slate-400 transition-colors ${className}`}
        title="본인 변경 내역을 삭제하고 운영팀 디폴트로 되돌립니다"
      >
        <RotateCcw size={12} />
        {label}
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-5">
            <div className="flex items-start justify-between mb-3">
              <h3 className="text-base font-semibold text-slate-900">변경 내역 리셋</h3>
              <button
                onClick={() => !busy && setOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X size={18} />
              </button>
            </div>
            <p className="text-sm text-slate-600 leading-relaxed mb-5">
              {confirmMessage || defaultMsg}
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setOpen(false)}
                disabled={busy}
                className="px-3 py-1.5 text-sm rounded border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                취소
              </button>
              <button
                onClick={handleReset}
                disabled={busy}
                className="px-3 py-1.5 text-sm rounded bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50"
              >
                {busy ? '리셋 중…' : '리셋'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
