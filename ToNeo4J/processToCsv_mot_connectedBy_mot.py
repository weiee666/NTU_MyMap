#!/usr/bin/env python3
"""Compute connections between motor roads based on geometry.

Input: neo4j_motor_roads.csv (from ToNeo4J/processToCsv_Node.py)
Logic:
- Parse geometry_points (JSON list of [lon, lat]) into LineString geometries in EPSG:4326.
- Project to EPSG:3414 (metres).
- For each pair of roads, they are considered connected if:
  * geometries intersect(), OR
  * minimum distance between them is <= 1 metre.
- Use spatial index to limit candidate pairs.

Output CSV: neo4j_mot_mot_rel.csv with columns:
    road_id_1, road_id_2, relation
and relation fixed as "ped_conncetedBy_ped" (按你的命名要求可调整)。
"""

import sys
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parent
MOT_ROADS_CSV = ROOT / "neo4j_motor_roads.csv"
OUTPUT_CSV = ROOT / "neo4j_mot_connectedBy_mot.csv"
GEO_CRS = "EPSG:4326"
PROJ_CRS = "EPSG:3414"
DISTANCE_THRESHOLD_M = 1.0
RELATION_LABEL = "mot_conncetedBy_mot"


def load_mot_roads() -> gpd.GeoDataFrame:
    if not MOT_ROADS_CSV.exists():
        raise FileNotFoundError(f"找不到机动车道路 CSV：{MOT_ROADS_CSV}")

    df = pd.read_csv(MOT_ROADS_CSV)
    if "geometry_points" not in df.columns:
        raise ValueError("输入 CSV 缺少 geometry_points 字段")

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
    if "road_id" not in gdf.columns:
        if "osm_id" in gdf.columns:
            gdf["road_id"] = gdf["osm_id"].astype(str)
        else:
            gdf["road_id"] = range(1, len(gdf) + 1)
    else:
        gdf["road_id"] = gdf["road_id"].astype(str)

    return gdf


def compute_connections(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    gdf_proj = gdf.to_crs(PROJ_CRS).reset_index(drop=True)

    sindex = gdf_proj.sindex
    if sindex is None:
        raise RuntimeError("无法创建空间索引，请确保安装 rtree 或 shapely>=2")

    relations = []

    for i, row_i in gdf_proj.iterrows():
        geom_i = row_i.geometry
        if geom_i is None or geom_i.is_empty:
            continue

        candidates = list(sindex.query(geom_i.buffer(DISTANCE_THRESHOLD_M), predicate="intersects"))
        for j in candidates:
            j = int(j)
            if j <= i:
                continue
            geom_j = gdf_proj.iloc[j].geometry
            if geom_j is None or geom_j.is_empty:
                continue

            intersects = geom_i.intersects(geom_j)
            near = False
            if not intersects:
                try:
                    near = geom_i.distance(geom_j) <= DISTANCE_THRESHOLD_M
                except Exception:
                    near = False

            if intersects or near:
                relations.append({
                    "road_id_1": gdf.iloc[int(i)]["road_id"],
                    "road_id_2": gdf.iloc[int(j)]["road_id"],
                    "relation": RELATION_LABEL,
                })

    if not relations:
        return pd.DataFrame(columns=["road_id_1", "road_id_2", "relation"])

    rel_df = pd.DataFrame(relations)
    rel_df.drop_duplicates(inplace=True)
    return rel_df


def main():
    try:
        mot_gdf = load_mot_roads()
        rel_df = compute_connections(mot_gdf)
        rel_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
        print(f"生成机动车道路间关系：{len(rel_df)} 条，输出到 {OUTPUT_CSV}")
        return 0
    except Exception as e:
        print(f"错误：{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
