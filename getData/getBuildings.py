import requests
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape, Point

# ----------------------
# 核心配置（NTU校园经纬度范围，可微调）
# ----------------------
# NTU校园大致边界（纬度lat：1.34~1.355，经度lon：103.67~103.69）
NTU_BBOX = "1.34,103.67,1.355,103.69"  # 格式：south,west,north,east
# 输出文件名称
OUTPUT_GEOJSON = "ntu_buildings.geojson"
OUTPUT_CSV = "ntu_buildings.csv"


# ----------------------
# 1. 从OSM Overpass API获取NTU建筑数据
# ----------------------
def get_ntu_buildings_from_osm(bbox):
    """
    调用Overpass API，获取NTU校园内所有建筑数据
    筛选字段：名称、建筑类型、楼层、几何轮廓、中心点坐标
    """
    # Overpass QL查询语句：精准筛选NTU校园内的建筑
    overpass_query = f"""
    [out:json][timeout:30];
    // 1. 筛选NTU校园范围内的建筑（way类型：面/多边形）
    (
      way["building"]({bbox});
      way["amenity"~"university|school|library|canteen|dormitory"]({bbox});
      way["name"~"Nanyang|NTU|Hall [0-9]|NS[0-9]|S[0-9]",i]({bbox});
    );
    // 2. 获取建筑的完整属性（名称、类型、楼层等）
    out body;
    >;
    out skel qt;
    """

    # 发送请求
    overpass_url = "https://overpass-api.de/api/interpreter"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(overpass_url, params={"data": overpass_query}, headers=headers)

    if response.status_code != 200:
        raise Exception(f"请求失败：{response.status_code}，请检查网络或Overpass API状态")

    return response.json()


# ----------------------
# 2. 解析OSM数据，提取核心字段
# ----------------------
def parse_osm_building_data(osm_json):
    """
    解析OSM返回的JSON，提取建筑的核心信息：
    - 名称、建筑类型、楼层、几何轮廓、中心点经纬度
    """
    buildings = []

    # 提取way（建筑多边形）
    ways = [elem for elem in osm_json["elements"] if elem["type"] == "way"]
    # 提取node（坐标点，用于拼接几何轮廓）
    nodes = {node["id"]: (node["lon"], node["lat"]) for node in osm_json["elements"] if node["type"] == "node"}

    for way in ways:
        # 1. 拼接建筑的几何轮廓（多边形坐标）
        if "nodes" not in way:
            continue
        way_nodes = [nodes[node_id] for node_id in way["nodes"] if node_id in nodes]
        if len(way_nodes) < 3:  # 至少3个点组成多边形
            continue

        # 2. 提取核心属性
        tags = way.get("tags", {})
        building_name = tags.get("name", "无名建筑")
        # 统一NTU建筑名称（修正OSM中的拼写/格式）
        if building_name.lower() in ["ntu", "nanyang technological university"]:
            building_name = "Nanyang Technological University (Main Campus)"

        # 3. 提取关键属性
        building_data = {
            "osm_id": way["id"],  # OSM唯一ID
            "name": building_name,
            "building_type": tags.get("building", tags.get("amenity", "unknown")),  # 建筑类型（图书馆/宿舍/教学楼）
            "floor": tags.get("addr:floor", tags.get("building:levels", "未知")),  # 楼层
            "campus": "NTU Singapore",
            # 几何轮廓（GeoJSON格式）
            "geometry": {
                "type": "Polygon",
                "coordinates": [way_nodes]
            },
            # 建筑中心点（用于和道路匹配）
            "centroid_lon": sum([p[0] for p in way_nodes]) / len(way_nodes),
            "centroid_lat": sum([p[1] for p in way_nodes]) / len(way_nodes)
        }

        buildings.append(building_data)

    return pd.DataFrame(buildings)


# ----------------------
# 3. 保存数据（GeoJSON/CSV）
# ----------------------
def save_building_data(building_df):
    """
    将解析后的建筑数据保存为GeoJSON（GIS/前端用）和CSV（表格分析用）
    """
    # 转为GeoDataFrame（支持空间操作）
    gdf = gpd.GeoDataFrame(
        building_df,
        geometry=[shape(geom) for geom in building_df["geometry"]],
        crs="EPSG:4326"  # 统一坐标系（WGS84）
    )

    # 删除重复建筑（按名称+中心点去重）
    gdf = gdf.drop_duplicates(subset=["name", "centroid_lon", "centroid_lat"])

    # 保存GeoJSON（可直接和道路数据融合）
    gdf.to_file(OUTPUT_GEOJSON, driver="GeoJSON", encoding="utf-8")
    # 保存CSV（方便查看/编辑）
    # 只保留非几何字段，便于表格处理
    csv_df = building_df.drop(columns=["geometry"])
    csv_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"数据保存完成！")
    print(f"- GeoJSON文件：{OUTPUT_GEOJSON}（共{len(gdf)}个建筑）")
    print(f"- CSV文件：{OUTPUT_CSV}")


# ----------------------
# 主函数：一键执行
# ----------------------
if __name__ == "__main__":
    try:
        # 1. 获取OSM数据
        print("正在从OSM获取NTU建筑数据...")
        osm_data = get_ntu_buildings_from_osm(NTU_BBOX)

        # 2. 解析数据
        print("正在解析建筑数据...")
        building_df = parse_osm_building_data(osm_data)

        # 3. 保存数据
        save_building_data(building_df)

        # 4. 输出示例数据（验证）
        print("\n示例建筑数据：")
        sample = building_df[["name", "building_type", "floor", "centroid_lat", "centroid_lon"]].head(3)
        print(sample)

    except Exception as e:
        print(f"执行出错：{str(e)}")