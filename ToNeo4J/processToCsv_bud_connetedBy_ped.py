#!/usr/bin/env python3
"""Create relationship CSV between buildings and pedestrian roads.

Rules:
- Load buildings from ntu_buildings.geojson and roads from ntu_roads.geojson.
- Limit roads to road_type in {footway, pedestrian, cycleway} (fallback to `highway` when needed).
- In projected CRS (SVY21, metres), detect if a building polygon intersects a road geometry or
  if their distance is < 10 metres.
- Record each matching pair as (building_osm_id, road_osm_id, relation="bud_conncetedBy_ped").

Output:
    neo4j_bud_connectedBy_ped.csv in the same folder as this script.
"""

import sys
import geopandas as gpd
import pandas as pd

# ----------------------
# Config
# ----------------------
BUILDING_FILE = "/Users/admin/Desktop/6321PROJECT1/getData/ntu_buildings.geojson"
ROAD_FILE = "/Users/admin/Desktop/6321PROJECT1/getData/ntu_roads.geojson"
OUTPUT_FILE = "/Users/admin/Desktop/6321PROJECT1/ToNeo4J/neo4j_bud_connectedBy_ped.csv"
PEDESTRIAN_TYPES = {"footway", "pedestrian", "cycleway"}
DISTANCE_THRESHOLD_M = 10.0
GEO_CRS = "EPSG:4326"
PROJ_CRS = "EPSG:3414"
RELATION_LABEL = "bud_conncetedBy_ped"


def load_geo_data():
    # 加载 GeoJSON 并准备好 building_id / road_id 字段
    buildings = gpd.read_file(BUILDING_FILE).set_crs(GEO_CRS, allow_override=True)
    roads = gpd.read_file(ROAD_FILE).set_crs(GEO_CRS, allow_override=True)

    buildings = buildings.dropna(subset=["geometry"]).copy().reset_index(drop=True)
    buildings["building_id"] = buildings.get("osm_id", range(1, len(buildings) + 1)).astype(str)

    roads = roads.dropna(subset=["geometry"]).copy().reset_index(drop=True)
    road_type_series = roads.get("road_type")
    highway_series = roads.get("highway")
    if road_type_series is None and highway_series is None:
        roads["road_type"] = "unknown"
    elif road_type_series is None:
        roads["road_type"] = highway_series
    else:
        roads["road_type"] = road_type_series
    if highway_series is not None:
        mask = roads["road_type"].isna() | (roads["road_type"].astype(str).str.strip() == "")
        roads.loc[mask, "road_type"] = highway_series[mask]
    roads["road_type"] = roads["road_type"].fillna("unknown").astype(str)

    roads["road_id"] = roads.get("osm_id", range(1, len(roads) + 1)).astype(str)

    ped_roads = roads[roads["road_type"].str.lower().isin(t.lower() for t in PEDESTRIAN_TYPES)].copy().reset_index(drop=True)

    if ped_roads.empty:
        raise ValueError("在给定的 road_type 中没有找到人行道路数据")

    return buildings, ped_roads


def compute_relationships(buildings, roads):
    # 使用投影坐标系来计算距离
    buildings_proj = buildings.to_crs(PROJ_CRS).reset_index(drop=True)
    roads_proj = roads.to_crs(PROJ_CRS).reset_index(drop=True)

    sindex = roads_proj.sindex
    if sindex is None:
        raise RuntimeError("无法创建道路空间索引，确保安装了 rtree 或 pygeos/shapely>=2")

    relations = []

    for b_idx, building in buildings_proj.iterrows():
        geom = building.geometry
        if geom is None or geom.is_empty:
            continue

        # 用 buffer + sindex 限定候选道路
        candidates_idx = list(sindex.query(geom.buffer(DISTANCE_THRESHOLD_M), predicate="intersects"))
        if not candidates_idx:
            continue

        for ridx in candidates_idx:
            road_geom = roads_proj.iloc[int(ridx)].geometry
            if road_geom is None or road_geom.is_empty:
                continue

            intersects = geom.intersects(road_geom)
            near = False
            if not intersects:
                try:
                    near = geom.distance(road_geom) <= DISTANCE_THRESHOLD_M
                except Exception:
                    near = False

            if intersects or near:
                # 直接使用 reset_index 后的 iloc 来取 building_id / road_id，避免 numpy 索引问题
                relations.append({
                    "building_id": buildings.iloc[int(b_idx)]["building_id"],
                    "road_id": roads.iloc[int(ridx)]["road_id"],
                    "relation": RELATION_LABEL
                })

    return relations


def main():
    try:
        buildings, roads = load_geo_data()
        relations = compute_relationships(buildings, roads)
        if not relations:
            print("未找到任何建筑-人行道路关系。")
            pd.DataFrame(columns=["building_id", "road_id", "relation"]).to_csv(
                OUTPUT_FILE, index=False, encoding="utf-8-sig"
            )
            return 0

        rel_df = pd.DataFrame(relations)
        rel_df.drop_duplicates(inplace=True)
        rel_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        print(f"生成 {len(rel_df)} 条建筑-人行道路关系：{OUTPUT_FILE}")
        return 0
    except Exception as exc:
        print(f"错误：{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
