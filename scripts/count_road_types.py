#!/usr/bin/env python3
"""Count unique values of `road_type` in a GeoJSON of roads.

Usage:
    python3 scripts/count_road_types.py [path/to/ntu_roads.geojson]

If geopandas is installed it will be used to read the file; otherwise the script falls
back to using the json module + pandas to parse feature.properties.
"""
import sys
import json
from pathlib import Path

try:
    import geopandas as gpd
    HAS_GPD = True
except Exception:
    HAS_GPD = False

import pandas as pd

DEFAULT_PATH = Path(__file__).resolve().parents[1] / 'getData' / 'ntu_roads.geojson'


def load_geojson(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if HAS_GPD:
        # geopandas will produce a GeoDataFrame; convert to DataFrame but keep property columns
        gdf = gpd.read_file(path)
        # If geometry column exists, drop it for plain pandas operations
        if 'geometry' in gdf.columns:
            df = pd.DataFrame(gdf.drop(columns=['geometry']))
        else:
            df = pd.DataFrame(gdf)
        return df
    else:
        with path.open('r', encoding='utf-8') as f:
            obj = json.load(f)
        features = obj.get('features', []) if isinstance(obj, dict) else []
        props = [feat.get('properties', {}) for feat in features]
        df = pd.json_normalize(props)
        return df


def summarize_road_type(df: pd.DataFrame):
    # Common field names to try if 'road_type' not present
    candidates = ['road_type', 'highway', 'type']
    field = None
    for c in candidates:
        if c in df.columns:
            field = c
            break

    if field is None:
        print("No obvious 'road_type' field found in the data. Available columns:")
        print(list(df.columns))
        return 1

    series = df[field]
    counts = series.fillna('<NULL>').value_counts()
    unique_count = series.nunique(dropna=False)

    print(f"Using field: '{field}'")
    print(f"Unique types (including NULL): {unique_count}\n")
    print(counts.to_string())
    return 0


def main(argv):
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_PATH
    try:
        df = load_geojson(path)
    except Exception as e:
        print(f"Failed to load GeoJSON: {e}")
        return 2

    return summarize_road_type(df)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
