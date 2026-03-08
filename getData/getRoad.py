import requests
import geopandas as gpd
import pandas as pd
from shapely.geometry import shape, LineString

# ----------------------
# 核心配置（和建筑脚本完全对齐）
# ----------------------
# NTU校园经纬度边界（south,west,north,east），和建筑脚本保持一致
NTU_BBOX = "1.34,103.67,1.355,103.69"
# 输出文件名称（便于和建筑数据对应）
OUTPUT_GEOJSON = "ntu_roads.geojson"
OUTPUT_CSV = "ntu_roads.csv"


# ----------------------
# 1. 从OSM Overpass API获取NTU道路数据
# ----------------------
def get_ntu_roads_from_osm(bbox):
    """
    调用Overpass API，精准筛选NTU校园内的道路数据
    包含：主干道、支路、人行道、自行车道、连廊等校园内道路
    """
    # Overpass QL查询：筛选NTU范围内所有道路类型
    overpass_query = f"""
    [out:json][timeout:30];
    // 1. 筛选NTU校园内的道路（way类型：线）
    (
      // 核心道路类型：主干道/次干道/支路/人行道/自行车道/校园内部道路
      way["highway"~"primary|secondary|tertiary|residential|service|footway|cycleway|pedestrian|path"]({bbox});
      // 补充筛选NTU相关命名的道路（避免漏检校内小路）
      way["name"~"Nanyang|NTU|Campus|Hall [0-9]",i]({bbox});
    );
    // 2. 获取道路完整属性（名称、类型、通行规则等）
    out body;
    >;
    out skel qt;
    """

    # 发送请求（和建筑脚本相同的请求头，避免被拦截）
    overpass_url = "https://overpass-api.de/api/interpreter"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(overpass_url, params={"data": overpass_query}, headers=headers)

    if response.status_code != 200:
        raise Exception(f"请求失败：{response.status_code}，请检查网络或Overpass API状态")

    return response.json()


# ----------------------
# 2. 解析OSM数据，提取道路核心字段
# ----------------------
def parse_osm_road_data(osm_json):
    """
    解析OSM返回的JSON，提取道路核心信息：
    - 名称、道路类型、通行方式、几何线路、中心点坐标（用于匹配建筑）
    """
    roads = []

    # 提取way（道路线）
    ways = [elem for elem in osm_json["elements"] if elem["type"] == "way"]
    # 提取node（坐标点，用于拼接道路几何线路）
    nodes = {node["id"]: (node["lon"], node["lat"]) for node in osm_json["elements"] if node["type"] == "node"}

    for way in ways:
        # 1. 拼接道路的几何线路（线坐标）
        if "nodes" not in way:
            continue
        way_nodes = [nodes[node_id] for node_id in way["nodes"] if node_id in nodes]
        if len(way_nodes) < 2:  # 至少2个点组成线
            continue

        # 2. 提取核心属性
        tags = way.get("tags", {})
        road_name = tags.get("name", "无名道路")
        # 统一NTU道路名称格式（修正OSM拼写）
        if road_name.lower() in ["ntu campus road", "nanyang ave"]:
            road_name = f"NTU {road_name.capitalize()}"

        # 3. 提取关键属性（适配校园场景）
        road_data = {
            "osm_id": way["id"],  # OSM唯一ID
            "name": road_name,
            "road_type": tags.get("highway", "unknown"),  # 道路类型（primary/footway等）
            "oneway": tags.get("oneway", "no"),  # 是否单向通行
            "cycleway": tags.get("cycleway", "no"),  # 是否允许自行车
            "campus": "NTU Singapore",
            # 几何线路（GeoJSON格式）
            "geometry": {
                "type": "LineString",
                "coordinates": way_nodes
            },
            # 道路中心点（用于和建筑匹配）
            "centroid_lon": sum([p[0] for p in way_nodes]) / len(way_nodes),
            "centroid_lat": sum([p[1] for p in way_nodes]) / len(way_nodes)
        }

        roads.append(road_data)

    return pd.DataFrame(roads)


# ----------------------
# 3. 保存数据（GeoJSON/CSV，和建筑脚本格式一致）
# ----------------------
def save_road_data(road_df):
    """
    保存道路数据为GeoJSON（GIS/前端用）和CSV（表格分析用）
    格式和建筑数据完全对齐，便于后续融合匹配
    """
    # 转为GeoDataFrame（支持空间操作）
    gdf = gpd.GeoDataFrame(
        road_df,
        geometry=[shape(geom) for geom in road_df["geometry"]],
        crs="EPSG:4326"  # 和建筑数据统一坐标系（WGS84）
    )

    # 删除重复道路（按名称+中心点去重）
    gdf = gdf.drop_duplicates(subset=["name", "centroid_lon", "centroid_lat"])

    # 保存GeoJSON（可直接和建筑数据融合）
    gdf.to_file(OUTPUT_GEOJSON, driver="GeoJSON", encoding="utf-8")
    # 保存CSV（方便查看/编辑）
    csv_df = road_df.drop(columns=["geometry"])
    csv_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"数据保存完成！")
    print(f"- GeoJSON文件：{OUTPUT_GEOJSON}（共{len(gdf)}条道路）")
    print(f"- CSV文件：{OUTPUT_CSV}")


# ----------------------
# 主函数：一键执行（和建筑脚本逻辑完全一致）
# ----------------------
if __name__ == "__main__":
    try:
        # 1. 获取OSM数据
        print("正在从OSM获取NTU道路数据...")
        osm_data = get_ntu_roads_from_osm(NTU_BBOX)

        # 2. 解析数据
        print("正在解析道路数据...")
        road_df = parse_osm_road_data(osm_data)

        # 3. 保存数据
        save_road_data(road_df)

        # 4. 输出示例数据（验证）
        print("\n示例道路数据：")
        sample = road_df[["name", "road_type", "oneway", "centroid_lat", "centroid_lon"]].head(3)
        print(sample)

    except Exception as e:
        print(f"执行出错：{str(e)}")