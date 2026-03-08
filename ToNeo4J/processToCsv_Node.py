import json
import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

# ----------------------
# 核心配置
# ----------------------
BUILDING_FILE = "/Users/admin/Desktop/6321PROJECT1/getData/ntu_buildings.geojson"
ROAD_FILE = "/Users/admin/Desktop/6321PROJECT1/getData/ntu_roads.geojson"
OUTPUT_BUILDINGS = "/Users/admin/Desktop/6321PROJECT1/ToNeo4J/neo4j_buildings.csv"
OUTPUT_PEDESTRIAN_ROADS = "/Users/admin/Desktop/6321PROJECT1/ToNeo4J/neo4j_pedestrian_roads.csv"
OUTPUT_MOTOR_ROADS = "/Users/admin/Desktop/6321PROJECT1/ToNeo4J/neo4j_motor_roads.csv"
PEDESTRIAN_ROAD_TYPES = {"footway", "pedestrian", "cycleway"}
MOTOR_ROAD_TYPES = {"service", "primary", "residential"}
GEO_CRS = "EPSG:4326"  # WGS84（经纬度，用于Neo4j存储）
PROJ_CRS = "EPSG:3414"  # 新加坡SVY21（米为单位，用于距离/长度计算）


# ----------------------
# 1. 加载并预处理数据
# ----------------------
def load_and_preprocess_data():
    """加载 GeoJSON，标准化字段，并补充几何信息（质心、长度等）。"""
    buildings = gpd.read_file(BUILDING_FILE).set_crs(GEO_CRS, allow_override=True)
    roads = gpd.read_file(ROAD_FILE).set_crs(GEO_CRS, allow_override=True)

    # ========== 建筑 ==========
    buildings = buildings.dropna(subset=["name", "geometry"]).copy()
    buildings["building_id"] = buildings.get("osm_id", range(1, len(buildings) + 1)).astype(str)
    buildings_proj = buildings.to_crs(PROJ_CRS)
    centroids_proj = buildings_proj.geometry.centroid
    centroids_geo = gpd.GeoSeries(centroids_proj, crs=PROJ_CRS).to_crs(GEO_CRS)
    buildings["lat"] = centroids_geo.y
    buildings["lon"] = centroids_geo.x

    # ========== 道路 ==========
    roads = roads.dropna(subset=["geometry"]).copy()
    roads["road_id"] = roads.get("osm_id", range(1, len(roads) + 1)).astype(str)
    roads["road_name"] = roads.get("name", "").fillna("无名道路")
    road_type_series = roads.get("road_type")
    highway_series = roads.get("highway")
    if road_type_series is None:
        if highway_series is not None:
            roads["road_type"] = highway_series
        else:
            roads["road_type"] = pd.Series(["unknown"] * len(roads), index=roads.index)
    else:
        roads["road_type"] = road_type_series
    if highway_series is not None:
        mask = roads["road_type"].isna() | (roads["road_type"].astype(str).str.strip() == "")
        roads.loc[mask, "road_type"] = highway_series[mask]
    roads["road_type"] = roads["road_type"].fillna("unknown").replace("", "unknown").astype(str)
    roads_proj = roads.to_crs(PROJ_CRS)
    roads["length_m"] = roads_proj.geometry.length.round(2)

    print(f"加载完成：{len(buildings)} 个建筑，{len(roads)} 条道路")
    return buildings, roads


# ----------------------
# 2. 辅助方法
# ----------------------
def geometry_to_coordinate_string(geom):
    """把几何的坐标序列转为 JSON 字符串，便于写入 CSV。"""
    if geom is None or geom.is_empty:
        return ""
    coords = mapping(geom)["coordinates"]
    return json.dumps(coords)


def export_with_geometry(gdf, output_path, description):
    """把 GeoDataFrame 写成 CSV，附带 geometry_points 字段。"""
    export_df = gdf.copy()
    export_df["geometry_points"] = export_df.geometry.apply(geometry_to_coordinate_string)
    export_df = export_df.drop(columns="geometry")
    export_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"- {description}：{output_path}（{len(export_df)} 条）")


def filter_roads_by_type(roads, allowed_types):
    allowed = {t.lower() for t in allowed_types}
    return roads[roads["road_type"].str.lower().isin(allowed)].copy()


# ----------------------
# 3. 导出节点 CSV
# ----------------------
def export_building_nodes(buildings):
    export_with_geometry(buildings, OUTPUT_BUILDINGS, "建筑节点")


def export_pedestrian_roads(roads):
    subset = filter_roads_by_type(roads, PEDESTRIAN_ROAD_TYPES)
    export_with_geometry(subset, OUTPUT_PEDESTRIAN_ROADS, "人行道路节点")


def export_motor_roads(roads):
    subset = filter_roads_by_type(roads, MOTOR_ROAD_TYPES)
    export_with_geometry(subset, OUTPUT_MOTOR_ROADS, "机动车道路节点")


# ----------------------
# 主函数
# ----------------------
if __name__ == "__main__":
    try:
        buildings_df, roads_df = load_and_preprocess_data()
        export_building_nodes(buildings_df)
        export_pedestrian_roads(roads_df)
        export_motor_roads(roads_df)
        print("\n🎉 节点 CSV 导出完成！关系边将在其他脚本中处理。")
    except Exception as e:
        print(f"\n❌ 执行出错：{str(e)}")
        import traceback

        traceback.print_exc()

