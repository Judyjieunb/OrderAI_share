"""PLC 엔진 v2 데이터 클래스 정의."""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Literal, Optional

import pandas as pd


@dataclass(frozen=True)
class BrandSpec:
    brand_code: str
    brand_name: str
    avg_size_stock_threshold: int = 100
    has_tax_free: bool = True
    scale_blend: float = 0.5
    plc_exclude_prods: list[str] = field(default_factory=list)
    item_nm_map_path: str = ""
    store_count: Optional[int] = None
    broken_coverage_ratio: float = 0.667  # 1/3 매장 배분 불가 기준

    def __post_init__(self):
        if not self.has_tax_free and self.scale_blend != 0.0:
            object.__setattr__(self, 'scale_blend', 0.0)

    @classmethod
    def from_json(cls, path: str, brand_code: str) -> BrandSpec:
        data = json.load(open(path))
        brand = dict(data["brands"][brand_code])
        # store_count × broken_coverage_ratio 자동 계산 (수동 avg_size_stock_threshold 있으면 우선)
        if 'avg_size_stock_threshold' not in brand and brand.get('store_count'):
            brand['avg_size_stock_threshold'] = round(
                brand['store_count'] * brand.get('broken_coverage_ratio', 0.667)
            )
        return cls(**brand)

    def load_item_nm_map(self) -> dict[str, str]:
        if not self.item_nm_map_path:
            return {}
        return json.load(open(self.item_nm_map_path))


@dataclass(frozen=True)
class SeasonSpec:
    season_code: str
    season_type: Literal["fw", "ss"]
    seasons_for_plc: list[str] = field(default_factory=list)
    fwo_range: tuple[int, int] = (1, 39)
    sale_col: str = "SC_SALE_QTY_TAX"

    @classmethod
    def from_json(cls, path: str, season_code: str) -> SeasonSpec:
        data = json.load(open(path))
        seasons_cfg = data.get("seasons", {})
        if season_code in seasons_cfg:
            s = dict(seasons_cfg[season_code])
            s["fwo_range"] = tuple(s["fwo_range"])
            return cls(**s)
        # Fallback: season_code 끝 글자로 type 자동 도출 + 표준 디폴트.
        if not season_code or season_code[-1].upper() not in ('F', 'S'):
            raise RuntimeError(
                f"season_code={season_code!r} 끝 글자가 F/S 가 아님 — type 도출 불가."
            )
        season_type = 'fw' if season_code[-1].upper() == 'F' else 'ss'
        try:
            year_int = int(season_code[:-1])
        except ValueError:
            raise RuntimeError(
                f"season_code={season_code!r} 의 연도 부분이 정수 아님."
            )
        type_char = season_code[-1]
        plc_seasons = [f"{y:02d}{type_char}" for y in range(year_int - 2, year_int + 1)]
        print(
            f"[INFO] plc_engine_config.json::seasons[{season_code!r}] 미등록 — "
            f"자동 fallback (type={season_type}, seasons_for_plc={plc_seasons}, "
            f"fwo_range=(1,39), sale_col=SC_SALE_QTY_TAX). 커스텀 필요 시 명시 등록."
        )
        return cls(
            season_code=season_code,
            season_type=season_type,
            seasons_for_plc=plc_seasons,
            fwo_range=(1, 39),
            sale_col='SC_SALE_QTY_TAX',
        )

    def fw_order(self, week: int) -> int:
        if self.season_type == "fw":
            return week - 22 if week >= 23 else week + 30
        if self.season_type == "ss":
            return week - 48 if week >= 49 else week + 4
        raise ValueError(f"Unknown season_type: {self.season_type}")

    def fwo_to_label(self, fwo: int) -> str:
        if self.season_type == "fw":
            wk = fwo + 22 if fwo <= 30 else fwo - 30
            return f"W{wk:02d}"
        if self.season_type == "ss":
            wk = fwo + 48 if fwo <= 4 else fwo - 4
            return f"W{wk:02d}"
        raise ValueError(f"Unknown season_type: {self.season_type}")


@dataclass(frozen=True)
class EngineParams:
    dtw_min_window: int = 4
    dtw_warp_band: int = 2
    dtw_shift_high: int = 6
    dtw_shift_medium: int = 3
    dtw_dist_high: float = 0.029
    dtw_dist_medium: float = 0.085
    min_sale_weeks: int = 4
    min_cum_intake: int = 50
    min_sc_for_plc: int = 5
    dead_stock_weeks: int = 2
    plc_tail_decay: float = 0.7

    @classmethod
    def from_json(cls, path: str, brand_code: str) -> EngineParams:
        data = json.load(open(path))
        ep = data["engine_params"]
        merged = {**ep["default"], **ep.get(brand_code, {})}
        return cls(**merged)


@dataclass(frozen=True)
class EngineInputs:
    gt: pd.DataFrame
    restored: Optional[pd.DataFrame]  # None이면 GT의 ADJ 컬럼 사용
    weekly_raw: pd.DataFrame
    plc_ratio: pd.DataFrame


@dataclass(frozen=True)
class BrokenPoint:
    week: int
    pos: int
    avg_size_stock: float = 0.0


@dataclass
class EngineResult:
    sc_predictions: dict  # (prod_cd, color_cd) -> dict
    style_aggregates: dict  # prod_cd -> dict
    metrics: dict
