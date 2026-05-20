"""AI Sales Loss V3 — S5 PLC 엔진 기반 기회비용 계산기 (얇은 러너)

GT/복원/PLC 미존재 시 FileNotFoundError (fail fast).

V3 부터 S5 PLC 엔진 사용 (이전 V2 감쇠모델 코드는 order-ai-share 에서 제외됨).
"""
import json
import math
import os
import pandas as pd
from pathlib import Path
from config_loader import (
    get_gt_path, get_restored_path, get_plc_forecast_path,
    get_weekly_data_path, get_timeseries_output_path, get_dashboard_json_path,
    get_target_sell_through, load_plc_engine_specs,
    get_shortage_loss_thresholds,
)
from plc_engine import run_engine
from plc_engine.specs import EngineInputs

print("=" * 60)
print("Step 3: AI 수요 예측 (S5 PLC 엔진 v2)")
print("=" * 60)

TARGET_SELL_THROUGH = get_target_sell_through()


def main():
    brand_spec, season_spec, engine_params = load_plc_engine_specs()
    print(f"  [{brand_spec.brand_name} {season_spec.season_code}] 엔진 실행")

    weekly_path = get_weekly_data_path()
    weekly_csv_fallback = weekly_path.replace('.xlsx', '.csv')
    for name, p in [("GT", get_gt_path()),
                    ("PLC", get_plc_forecast_path())]:
        if not Path(p).exists():
            raise FileNotFoundError(f"엔진 입력 파일 없음: {name} ({p})")
    # 주간데이터는 csv(Snowflake 캐시) 또는 xlsx 둘 중 하나만 있어도 OK
    if not Path(weekly_path).exists() and not Path(weekly_csv_fallback).exists():
        raise FileNotFoundError(
            f"엔진 입력 파일 없음: 주간데이터 ({weekly_path} 또는 {weekly_csv_fallback})"
        )

    # CSV 우선 사용 (Snowflake 최신 데이터, xlsx보다 범위 넓음)
    if os.path.exists(weekly_csv_fallback):
        weekly_df = pd.read_csv(weekly_csv_fallback)
    elif weekly_path.endswith('.xlsx'):
        weekly_df = pd.read_excel(weekly_path)
    else:
        weekly_df = pd.read_csv(weekly_path)

    # GT에 ADJ_SC_SALE_QTY_TAX 통합 → restored 별도 로드 불필요
    gt_df = pd.read_csv(get_gt_path())
    restored_df = None
    restored_path = Path(get_restored_path())
    if restored_path.exists() and 'ADJ_SC_SALE_QTY_TAX' not in gt_df.columns:
        restored_df = pd.read_csv(restored_path)
        print("  [복원 데이터] 별도 파일 로드")
    else:
        print("  [복원 데이터] GT 통합 (ADJ_SC_SALE_QTY_TAX)")

    inputs = EngineInputs(
        gt=gt_df,
        restored=restored_df,
        weekly_raw=weekly_df,
        plc_ratio=pd.read_csv(get_plc_forecast_path()),
    )

    result = run_engine(brand_spec, season_spec, engine_params, inputs)
    m = result.metrics
    print(f"  SC: {len(result.sc_predictions)}, "
          f"DTW P25: {m.get('dtw_dist_p25', 0):.3f}, "
          f"기회비용: {m.get('total_lost_qty', 0):,}장")

    update_excel(result)
    update_dashboard_json(result)
    update_past_styles_json()


def update_excel(result):
    """Excel 'AI 계산 기회비용', 'AI제안 발주량' 컬럼 갱신.

    Top 5% 대물량 스타일은 70% 목표판매율, 나머지는 65% (기본) — brand_config 기반.
    의류 PART_CD만 분류 대상 (timeseries Excel은 weekly_analysis에서 이미 의류 필터링됨).
    """
    from config_loader import get_high_volume_target_sell_through, get_high_volume_top_percent

    base_target = TARGET_SELL_THROUGH  # 0.65
    high_target = get_high_volume_target_sell_through()  # 0.70
    top_pct = get_high_volume_top_percent()  # 5

    excel_path = get_timeseries_output_path()
    df = pd.read_excel(excel_path)

    if 'AI 계산 기회비용' not in df.columns:
        df['AI 계산 기회비용'] = 0
    if 'AI제안 발주량' not in df.columns:
        df['AI제안 발주량'] = 0

    # === Pass 1: AI 기회비용 산출 + 당해 시즌 PART_CD별 잠재수요 집계 ===
    # (Top 5% 분류는 당해 시즌만 대상. 전년/재작년 PART_CD는 default base target 적용)
    matched, total = 0, 0
    style_potential = {}  # 당해 PART_CD -> 잠재수요 합

    for idx, row in df.iterrows():
        pc = row.get('PART_CD')
        cc = row.get('COLOR_CD')
        if pd.isna(pc) or pd.isna(cc):
            continue
        total += 1
        sc = result.sc_predictions.get((pc, cc))
        loss = sc['lost_qty'] if sc is not None else 0
        if sc is not None:
            matched += 1
        df.at[idx, 'AI 계산 기회비용'] = loss

        # 잠재수요 집계는 당해 시즌만 (PERIOD == '당해')
        period = str(row.get('PERIOD', '당해'))
        if period != '당해':
            continue
        total_sale = float(row.get('총판매', 0) or 0)
        potential = total_sale + loss
        if potential > 0:
            pc_str = str(pc)
            style_potential[pc_str] = style_potential.get(pc_str, 0) + potential

    # === Top N% 대물량 PART_CD 식별 (당해 의류 잠재수요 기준) ===
    sorted_styles = sorted(style_potential.items(), key=lambda x: -x[1])
    n_styles = len(sorted_styles)
    n_top = max(1, int(n_styles * top_pct / 100)) if n_styles > 0 else 0
    top_set = set(pc for pc, _ in sorted_styles[:n_top])

    print(f"  * 대물량 분류 (당해 의류): Top {top_pct}% = {n_top}/{n_styles} PART_CD (목표판매율 {high_target:.0%})")
    print(f"    일반 스타일 {n_styles - n_top}개 목표판매율 {base_target:.0%} 적용")

    # === Pass 2: 차등 target으로 AI제안 발주량 산출 (모든 row 처리) ===
    for idx, row in df.iterrows():
        pc = row.get('PART_CD')
        if pd.isna(pc):
            df.at[idx, 'AI제안 발주량'] = 0
            continue
        loss = df.at[idx, 'AI 계산 기회비용']
        total_sale = float(row.get('총판매', 0) or 0)
        if total_sale + loss > 0:
            target = high_target if str(pc) in top_set else base_target
            order = math.ceil((total_sale + loss) / target / 10) * 10
        else:
            order = 0
        df.at[idx, 'AI제안 발주량'] = int(order)

    df.to_excel(excel_path, index=False)
    coverage = matched / max(total, 1)
    print(f"  * Excel 업데이트: {matched}/{total} ({coverage:.1%})")


def _build_json_date_to_woy(weekly_path):
    """weekly_raw END_DT로부터 JSON date(MM/DD) → WEEK_OF_YEAR 매핑 구축.
    .csv 우선 사용 (Snowflake 최신 데이터 포함), .xlsx fallback."""
    csv_path = weekly_path.replace('.xlsx', '.csv')
    if os.path.exists(csv_path):
        wr = pd.read_csv(csv_path)
    elif weekly_path.endswith('.xlsx'):
        wr = pd.read_excel(weekly_path)
    else:
        wr = pd.read_csv(weekly_path)
    wr = wr[wr['PERIOD'] == '당해'].copy()
    wr['END_DT'] = pd.to_datetime(wr['END_DT'])
    wr['WOY'] = wr['END_DT'].dt.isocalendar().week.astype(int)
    wr['DATE_LABEL'] = wr['END_DT'].dt.strftime('%m/%d')
    return dict(zip(wr['DATE_LABEL'], wr['WOY']))


def update_dashboard_json(result):
    """JSON chartData에 potential_sale/loss 주입 + total 재집계.

    analysis 블록에 'AI제안 발주량' 추가 (timeseries Excel에서 lookup) — ref-style endpoint에서 활용.
    """
    json_path = get_dashboard_json_path()
    data = json.loads(Path(json_path).read_text(encoding='utf-8'))

    json_date_to_woy = _build_json_date_to_woy(get_weekly_data_path())

    # timeseries Excel에서 (PART_CD, COLOR_CD) → AI제안 발주량 매핑 구축 (analysis 블록 보강용)
    ai_order_map: dict = {}
    try:
        excel_path = get_timeseries_output_path()
        df_excel = pd.read_excel(excel_path)
        for _, row in df_excel.iterrows():
            pc = str(row.get('PART_CD', '')).strip()
            cc = str(row.get('COLOR_CD', '')).strip()
            if pc and cc:
                ai_order_map[(pc, cc)] = int(pd.to_numeric(row.get('AI제안 발주량', 0), errors='coerce') or 0)
    except Exception as e:
        print(f"  ⚠ AI제안 발주량 매핑 로드 실패: {e}")

    def _sale_or_zero(p):
        try:
            return int(p.get('sale', 0))
        except (TypeError, ValueError):
            return 0

    matched_sc, total_sc = 0, 0
    week_matched, week_total = 0, 0

    for diagnosis in ['hit', 'normal', 'shortage', 'risk']:
        for entry in data.get(diagnosis, []):
            colors_data = entry.get('colors', {})

            for color_key, color_data in colors_data.items():
                part_cd = color_data.get('itemInfo', {}).get('code')
                if not part_cd:
                    continue
                total_sc += 1
                sc = result.sc_predictions.get((part_cd, color_key))

                if sc is None:
                    for point in color_data.get('chartData', []):
                        point['potential_sale'] = 0
                        point['loss'] = 0
                        point['actual_tax'] = 0
                        point['predicted_sc'] = 0
                    continue

                matched_sc += 1
                woy_map = {woy: i for i, woy in enumerate(sc['week_numbers'])}

                # 결품(브로큰) 감지 안 된 SC는 PLC 예측선/loss 표시 안 함
                # (설계: 결품 시점부터 PLC 예측 그래프를 그림)
                if sc.get('broken') is None:
                    for point in color_data.get('chartData', []):
                        week_total += 1
                        date_key = point.get('date')
                        woy = json_date_to_woy.get(date_key)
                        if woy is not None and woy in woy_map:
                            week_matched += 1
                            point['actual_tax'] = int(sc['actuals_tax'][woy_map[woy]])
                        else:
                            point['actual_tax'] = 0
                        point['potential_sale'] = 0
                        point['predicted_sc'] = 0
                        point['loss'] = 0
                    analysis = color_data.setdefault('analysis', {})
                    analysis['예상손실수량'] = 0
                    analysis['AI제안 발주량'] = ai_order_map.get((part_cd, color_key), 0)
                    continue

                is_broken_series = sc.get('is_broken_series', [])
                for point in color_data.get('chartData', []):
                    week_total += 1
                    date_key = point.get('date')
                    woy = json_date_to_woy.get(date_key)
                    if woy is not None and woy in woy_map:
                        week_matched += 1
                        i = woy_map[woy]
                        point['potential_sale'] = float(sc['predicted_total'][i])
                        point['predicted_sc'] = float(sc['predicted_sc'][i])
                        point['actual_tax'] = int(sc['actuals_tax'][i])
                        sale = _sale_or_zero(point)
                        # 주차별 결품 상태 기반 loss 계산 (결품 주차만, 재입고 후 해소 주차는 0)
                        point['is_broken'] = bool(is_broken_series[i]) if i < len(is_broken_series) else False
                        if point['is_broken']:
                            point['loss'] = max(0, point['potential_sale'] - sale)
                        else:
                            point['loss'] = 0
                    else:
                        point['potential_sale'] = _sale_or_zero(point)
                        point['predicted_sc'] = 0
                        point['actual_tax'] = 0
                        point['loss'] = 0
                        point['is_broken'] = False

                analysis = color_data.setdefault('analysis', {})
                analysis['예상손실수량'] = sc['lost_qty']
                analysis['AI제안 발주량'] = ai_order_map.get((part_cd, color_key), 0)

            # total.chartData 재집계
            total_block = entry.get('total')
            if total_block and 'chartData' in total_block:
                date_prediction_sum = {}
                date_loss_sum = {}
                date_actual_tax_sum = {}
                date_predicted_sc_sum = {}
                for color_key, color_data in colors_data.items():
                    for point in color_data.get('chartData', []):
                        d = point.get('date')
                        if not d:
                            continue
                        # 결품 미감지 컬러: 예측값=0이지만 실판매 자체가 잠재 수요.
                        # 전체수요 fallback ← sale, 국내수요 fallback ← actual_tax.
                        ps = point.get('potential_sale', 0) or _sale_or_zero(point)
                        psc = point.get('predicted_sc', 0) or int(point.get('actual_tax', 0) or 0)
                        date_prediction_sum[d] = date_prediction_sum.get(d, 0) + ps
                        date_predicted_sc_sum[d] = date_predicted_sc_sum.get(d, 0) + psc
                        date_loss_sum[d] = date_loss_sum.get(d, 0) + point.get('loss', 0)
                        date_actual_tax_sum[d] = date_actual_tax_sum.get(d, 0) + point.get('actual_tax', 0)

                for point in total_block['chartData']:
                    d = point.get('date')
                    if d in date_prediction_sum:
                        point['potential_sale'] = date_prediction_sum[d]
                        point['loss'] = date_loss_sum.get(d, 0)
                        point['actual_tax'] = date_actual_tax_sum.get(d, 0)
                        point['predicted_sc'] = date_predicted_sc_sum.get(d, 0)
                    else:
                        point['potential_sale'] = _sale_or_zero(point)
                        point['loss'] = 0
                        point['actual_tax'] = 0
                        point['predicted_sc'] = 0

    # Shortage 재분류: loss 주입 완료 후 Hit/Normal 중 엄격 기준 통과분을 Shortage로 이동
    # (Risk는 유지 — 공급 부족으로 판매율 낮은 케이스는 Risk 특성 보존)
    moved = _reclassify_shortage(data)

    Path(json_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    sc_cov = matched_sc / max(total_sc, 1)
    wk_cov = week_matched / max(week_total, 1)
    print(f"  * JSON 업데이트: SC {matched_sc}/{total_sc} ({sc_cov:.1%}), weeks {week_matched}/{week_total} ({wk_cov:.1%})")
    print(f"  * Shortage 재분류 (엄격 기준): {moved['hit_to_shortage']}건(Hit→) + {moved['normal_to_shortage']}건(Normal→) 이동")
    # Engine→JSON은 100% (엔진 출력 전부 매핑). JSON→Engine은 GT 미포함 SC 때문에 <100% 정상.
    if matched_sc == 0:
        print("  [경고] JSON 매핑 SC 0건 — 식별자 불일치 의심")


def update_past_styles_json():
    """past_styles_data.json entries에 AI제안 발주량 사후 주입.

    weekly_analysis.py가 past_styles_data.json을 생성하는 시점은 ai_sales_loss_v3 실행 전이라
    analysis 블록에 'AI제안 발주량' 키가 없거나 0. 본 함수가 result.xlsx의 prev/prev2 row를
    읽어 (PART_CD, COLOR_CD) 단위로 사후 주입한다. dump_to_duckdb가 이 JSON을 그대로
    style_timeseries(period='prev'|'prev2')에 적재하므로, 결과적으로 과거 시즌 ref도
    DuckDB에서 AI발주량 lookup이 가능해진다.
    """
    project_root = Path(__file__).resolve().parent.parent
    paths = [
        project_root / 'output/past_styles_data.json',
        project_root / 'public/past_styles_data.json',
    ]
    paths = [p for p in paths if p.exists()]
    if not paths:
        print("  * past_styles_data.json 없음 → 스킵")
        return

    df = pd.read_excel(get_timeseries_output_path())
    color_ai_map: dict = {}
    style_ai_map: dict = {}
    for _, row in df.iterrows():
        pc = str(row.get('PART_CD', '')).strip()
        cc = str(row.get('COLOR_CD', '')).strip()
        period = str(row.get('PERIOD', ''))
        if not (pc and cc and period in ('전년', '재작년')):
            continue
        ai_order = int(pd.to_numeric(row.get('AI제안 발주량', 0), errors='coerce') or 0)
        color_ai_map[(pc, cc)] = ai_order
        style_ai_map[pc] = style_ai_map.get(pc, 0) + ai_order

    updated_styles = 0
    for path in paths:
        data = json.loads(path.read_text(encoding='utf-8'))
        for period_key in ('prev', 'prev2'):
            section = data.get(period_key) or {}
            for part_cd, entry in section.items():
                total = entry.get('total') or {}
                total_analysis = total.setdefault('analysis', {})
                total_analysis['AI제안 발주량'] = style_ai_map.get(part_cd, 0)
                colors = entry.get('colors') or {}
                for color_cd, color_data in colors.items():
                    cd_analysis = color_data.setdefault('analysis', {})
                    cd_analysis['AI제안 발주량'] = color_ai_map.get((part_cd, color_cd), 0)
                updated_styles += 1
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
        )
    print(f"  * past_styles 업데이트: {updated_styles}개 PART_CD × {len(paths)} 파일")


def _reclassify_shortage(data):
    """Hit/Normal 중 기회비용 엄격 기준 통과 스타일을 Shortage 탭으로 이동.

    기준: 장수 ≥ min_qty AND (비율 ≥ min_ratio OR 금액 ≥ min_amt)
    - Risk는 유지 (공급 부족이 판매율 하락 원인일 수 있으나 Risk 의미 보존)
    """
    t = get_shortage_loss_thresholds()
    moved_count = {'hit_to_shortage': 0, 'normal_to_shortage': 0}
    moved_items = []

    for source in ['hit', 'normal']:
        remaining = []
        for item in data.get(source, []):
            total = item.get('total', {})
            cd = total.get('chartData', [])
            info = total.get('itemInfo', {})
            lost_qty = sum(r.get('loss', 0) or 0 for r in cd)
            total_sale = sum(r.get('sale', 0) or 0 for r in cd)
            price = info.get('price', 0) or 0
            loss_amt = lost_qty * price
            loss_ratio = lost_qty / max(total_sale + lost_qty, 1)

            is_shortage = (
                lost_qty >= t['min_qty'] and
                (loss_ratio >= t['min_ratio'] or loss_amt >= t['min_amt'])
            )
            if is_shortage:
                moved_items.append(item)
                moved_count[f'{source}_to_shortage'] += 1
            else:
                remaining.append(item)
        data[source] = remaining

    data.setdefault('shortage', []).extend(moved_items)
    return moved_count


if __name__ == "__main__":
    main()
