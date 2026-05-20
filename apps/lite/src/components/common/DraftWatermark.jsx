import { FileWarning } from 'lucide-react'

/**
 * Lite 발주서 "검토용 초안" 워터마크 띠.
 *
 * 4/29 결정 (Model A): 담당자가 최종 확정자. 운영팀은 baseline 적재만.
 * 화면 표시는 이메일 제외 (Excel 워터마크에는 백엔드에서 자동 부착).
 *
 * Props:
 *   - className: 추가 클래스
 */
export default function DraftWatermark({ className = '' }) {
  return (
    <div
      className={`flex items-center gap-2 px-3 py-1.5 rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-xs ${className}`}
    >
      <FileWarning size={14} className="shrink-0" />
      <span>
        <strong className="font-semibold">검토용 초안</strong>
        <span className="text-amber-700/80"> · 담당자 최종 확정 전</span>
      </span>
    </div>
  )
}
