#!/usr/bin/env python3
"""Combine all relation CSVs into a single `relation.csv`.

Source files (in this folder):
- neo4j_bud_connectedBy_mot.csv       (building_id, road_id, relation)
- neo4j_bud_connectedBy_ped.csv       (building_id, road_id, relation)
- neo4j_mot_connectedBy_mot.csv       (road_id_1, road_id_2, relation)
- neo4j_ped_connectedBy_mot.csv       (ped_road_id, mot_road_id, relation)
- neo4j_ped_connectedBy_ped.csv       (road_id_1, road_id_2, relation)

All will be normalized to columns:
    source_id, target_id, relation

and concatenated into relation.csv in the same folder.
"""

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent

FILES_CONFIG = [
    {
        "path": ROOT / "neo4j_bud_connectedBy_mot.csv",
        "source_col": "building_id",
        "target_col": "road_id",
    },
    {
        "path": ROOT / "neo4j_bud_connectedBy_ped.csv",
        "source_col": "building_id",
        "target_col": "road_id",
    },
    {
        "path": ROOT / "neo4j_mot_connectedBy_mot.csv",
        "source_col": "road_id_1",
        "target_col": "road_id_2",
    },
    {
        "path": ROOT / "neo4j_ped_connectedBy_mot.csv",
        "source_col": "ped_road_id",
        "target_col": "mot_road_id",
    },
    {
        "path": ROOT / "neo4j_ped_connectedBy_ped.csv",
        "source_col": "road_id_1",
        "target_col": "road_id_2",
    },
]

OUTPUT_FILE = ROOT / "relation.csv"


def load_and_normalize(path: Path, source_col: str, target_col: str) -> pd.DataFrame:
    if not path.exists():
        print(f"警告：找不到文件 {path}，跳过。")
        return pd.DataFrame(columns=["source_id", "target_id", "relation"])

    df = pd.read_csv(path)
    missing = [c for c in (source_col, target_col, "relation") if c not in df.columns]
    if missing:
        print(f"警告：文件 {path} 缺少列 {missing}，跳过。")
        return pd.DataFrame(columns=["source_id", "target_id", "relation"])

    out = pd.DataFrame({
        "source_id": df[source_col].astype(str),
        "target_id": df[target_col].astype(str),
        "relation": df["relation"].astype(str),
    })
    return out


def main() -> int:
    frames = []
    for cfg in FILES_CONFIG:
        df_norm = load_and_normalize(cfg["path"], cfg["source_col"], cfg["target_col"])
        if not df_norm.empty:
            frames.append(df_norm)

    if not frames:
        print("未找到任何可用的关系数据，未生成 relation.csv。")
        return 0

    all_rel = pd.concat(frames, ignore_index=True)
    all_rel.drop_duplicates(inplace=True)
    all_rel.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"合并完成，共 {len(all_rel)} 条关系，输出到 {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
