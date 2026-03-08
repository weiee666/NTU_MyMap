#!/usr/bin/env python3
"""Compute connections between pedestrian roads and motor roads based on geometry.

Data source:
- Pedestrian roads: neo4j_pedestrian_roads.csv
- Motor roads: neo4j_motor_roads.csv

Logic:
- Parse geometry_points (JSON list of [lon, lat]) into LineString geometries in EPSG:4326.
- Project both to EPSG:3414 (metres).
- For each pedestrian road and each candidate motor road, they are considered connected if:
  * geometries intersect(), OR
  * minimum distance between them is <= 2 metres.
- Use spatial index on motor roads to limit candidate set for each pedestrian road.

Output CSV: neo4j_ped_connectedBy_mot.csv with columns:
    ped_road_id, mot_road_id, relation
and relation fixed as "ped_conncetedBy_mot".
"""

import sys
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parent
PED_ROADS_CSV = ROOT / "neo4j_pedestrian_roads.csv"
MOT_ROADS_CSV = ROOT / "neo4j_motor_roads.csv"
OUTPUT_CSV = ROOT / "neo4j_ped_connectedBy_mot.csv"
GEO_CRS = "EPSG:4326"
PROJ_CRS = "EPSG:3414"
DISTANCE_THRESHOLD_M = 2.0
RELATION_LABEL = "ped_conncetedBy_mot"


def _load_roads(csv_path: Path) -> gpd.GeoDataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"找不到 CSV：{csv_path}")

    df = pd.read_csv(csv_path)
    if "geometry_points" not in df.columns:
        raise ValueError(f"{csv_path} 缺少 geometry_points 字段")

    def parse_geom(s):
        if pd.isna(s) or s == "":
            return None
        try:
            coords = json.loads(s)
            if not coords:
                return None
            return LineString([(c[0], c[1]) for c in coords])
        except Exception:
            return None

    df["geometry"] = df["geometry_points"].apply(parse_geom)
    df = df.dropna(subset=["geometry"]).reset_index(drop=True)

    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs=GEO_CRS)
    # 统一 road_id 字段，优先使用已有 road_id，否则退回 osm_id
    if "road_id" not in gdf.columns:
        if "osm_id" in gdf.columns:
            gdf["road_id"] = gdf["osm_id"].astype(str)
        else:
            gdf["road_id"] = range(1, len(gdf) + 1)
    else:
        gdf["road_id"] = gdf["road_id"].astype(str)

    return gdf


def load_ped_and_mot():
    ped_gdf = _load_roads(PED_ROADS_CSV)
    mot_gdf = _load_roads(MOT_ROADS_CSV)
    return ped_gdf, mot_gdf


def compute_connections(ped_gdf: gpd.GeoDataFrame, mot_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    # 投影到米制坐标系
    ped_proj = ped_gdf.to_crs(PROJ_CRS).reset_index(drop=True)
    mot_proj = mot_gdf.to_crs(PROJ_CRS).reset_index(drop=True)

    sindex = mot_proj.sindex
    if sindex is None:
        raise RuntimeError("无法创建机动车道路空间索引，请确保安装 rtree 或 shapely>=2")

    relations = []

    for i, ped_row in ped_proj.iterrows():
        geom_ped = ped_row.geometry
        if geom_ped is None or geom_ped.is_empty:
            continue

        # 在 2m 缓冲区内找候选机动车道路
        candidates = list(sindex.query(geom_ped.buffer(DISTANCE_THRESHOLD_M), predicate="intersects"))
        if not candidates:
            continue

        for j in candidates:
            j = int(j)
            geom_mot = mot_proj.iloc[j].geometry
            if geom_mot is None or geom_mot.is_empty:
                continue

            intersects = geom_ped.intersects(geom_mot)
            near = False
            if not intersects:
                try:
                    near = geom_ped.distance(geom_mot) <= DISTANCE_THRESHOLD_M
                except Exception:
                    near = False

            if intersects or near:
                relations.append({
                    "ped_road_id": ped_gdf.iloc[int(i)]["road_id"],
                    "mot_road_id": mot_gdf.iloc[int(j)]["road_id"],
                    "relation": RELATION_LABEL,
                })

    if not relations:
        return pd.DataFrame(columns=["ped_road_id", "mot_road_id", "relation"])

    rel_df = pd.DataFrame(relations)
    rel_df.drop_duplicates(inplace=True)
    return rel_df


def main():
    try:
        ped_gdf, mot_gdf = load_ped_and_mot()
        rel_df = compute_connections(ped_gdf, mot_gdf)
        rel_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
        print(f"生成人行道-机动车道路关系：{len(rel_df)} 条，输出到 {OUTPUT_CSV}")
        return 0
    except Exception as e:
        print(f"错误：{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
