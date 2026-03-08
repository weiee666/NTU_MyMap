#!/usr/bin/env python3
"""Clip buildings and roads GeoJSON to the "Nanyang Technological University (Main Campus)" polygon.

Behavior:
- Find the campus polygon in getData/ntu_buildings.geojson by name == "Nanyang Technological University (Main Campus)".
- Backup original files (only once) to .backup.
- For buildings: keep only features whose geometry is fully within the campus polygon (geometry.within(campus)).
- For roads: keep only features that intersect the campus polygon (geometry.intersects(campus)).
- Overwrite the original geojson files with filtered results.

Usage:
    python3 dataClean/remove_out_Campus.py

"""
from pathlib import Path
import shutil
import sys
import datetime

try:
    import geopandas as gpd
    from shapely.geometry import shape
except Exception as e:
    print("This script requires geopandas and shapely. Install with: pip install geopandas shapely")
    raise

ROOT = Path(__file__).resolve().parents[1]
GETDATA = ROOT / 'getData'
BUILDINGS_F = GETDATA / 'ntu_buildings.geojson'
ROADS_F = GETDATA / 'ntu_roads.geojson'
CAMPUS_NAME = 'Nanyang Technological University (Main Campus)'

BACKUP_SUFFIX = '.backup'

def backup_file(p: Path):
    if not p.exists():
        return
    backup = p.with_suffix(p.suffix + BACKUP_SUFFIX)
    # if backup already exists, create timestamped backup
    if backup.exists():
        ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        backup = p.with_name(p.stem + f'.backup.{ts}' + p.suffix)
    shutil.copy2(p, backup)
    print(f'备份 {p} -> {backup}')


def main():
    if not BUILDINGS_F.exists():
        print('找不到文件:', BUILDINGS_F)
        return 2
    if not ROADS_F.exists():
        print('找不到文件:', ROADS_F)
        return 2

    print('加载建筑 GeoJSON...')
    buildings = gpd.read_file(BUILDINGS_F)
    # ensure CRS exists
    if buildings.crs is None:
        buildings.set_crs('EPSG:4326', inplace=True)

    # 寻找 campus feature
    campus_row = buildings[buildings.get('name') == CAMPUS_NAME]
    if campus_row.empty:
        # 尝试模糊匹配 (包含关键词)
        campus_row = buildings[buildings.get('name', '').str.contains('Nanyang Technological University', na=False)]
        if campus_row.empty:
            print('未能在 buildings GeoJSON 中找到校园边界，请确认名称。可用的 name 示例:')
            print(buildings.get('name').dropna().unique()[:20])
            return 3
        else:
            print(f"使用模糊匹配找到 {len(campus_row)} 条候选，取第一条作为校园边界: {campus_row.iloc[0].get('name')}")

    # 合并成单一的 polygon / multipolygon
    campus_geom = campus_row.geometry.unary_union
    print('校园边界已获取。类型：', campus_geom.geom_type)

    # 备份原文件（只做一次）
    backup_file(BUILDINGS_F)
    backup_file(ROADS_F)

    # 过滤建筑：仅保留完全位于校园内的建筑
    total_buildings = len(buildings)
    # note: some features (like the campus feature itself) might be part of buildings; keep campus itself
    def building_within(g):
        try:
            return g.within(campus_geom)
        except Exception:
            return False

    buildings_within = buildings[buildings.geometry.apply(building_within)].copy()

    # Ensure campus polygon feature remains (if present) to avoid losing it
    # If campus_row not within (it will be), add it
    if not campus_row.index.isin(buildings_within.index).any():
        buildings_within = gpd.GeoDataFrame(pd.concat([buildings_within, campus_row], ignore_index=True), crs=buildings.crs)

    kept_buildings = len(buildings_within)
    removed_buildings = total_buildings - kept_buildings
    print(f'建筑：总数 {total_buildings}，保留 {kept_buildings}，移除 {removed_buildings}')

    # 写回 buildings 文件（GeoJSON）
    buildings_within.to_file(BUILDINGS_F, driver='GeoJSON')
    print(f'已覆盖写回：{BUILDINGS_F}')

    # 处理道路：只保留与校园相交的道路（有部分落在校园内）
    print('加载道路 GeoJSON...')
    roads = gpd.read_file(ROADS_F)
    if roads.crs is None:
        roads.set_crs('EPSG:4326', inplace=True)

    # 如果 roads 与 buildings 有不同 CRS，则转换
    if roads.crs != buildings.crs:
        roads = roads.to_crs(buildings.crs)

    total_roads = len(roads)

    def road_intersects(g):
        try:
            return g.intersects(campus_geom)
        except Exception:
            return False

    roads_keep = roads[roads.geometry.apply(road_intersects)].copy()
    kept_roads = len(roads_keep)
    removed_roads = total_roads - kept_roads
    print(f'道路：总数 {total_roads}，保留 {kept_roads}，移除 {removed_roads}')

    # 写回 roads 文件
    roads_keep.to_file(ROADS_F, driver='GeoJSON')
    print(f'已覆盖写回：{ROADS_F}')

    print('\n处理完成。注意：已对原文件进行覆盖操作，备份保存在同目录下的 .backup 文件中。')
    return 0


if __name__ == '__main__':
    import pandas as pd
    sys.exit(main())
