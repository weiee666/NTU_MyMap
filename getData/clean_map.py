#!/usr/bin/env python3
"""Core XML node extraction helpers (minimal, no file/CLI code).

Only contains the essential functions to extract <node> elements
that include a tag with k="name". Designed to be imported and
used by other code; it performs no file I/O or argument parsing.
"""
from typing import Dict, Generator, Iterable, Optional, Tuple
import xml.etree.ElementTree as ET
import json
import argparse


def local_name(tag: str) -> str:
    """Return the local name of an XML tag (strip namespace)."""
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag


def extract_named_node_obj(elem: ET.Element) -> Optional[Dict[str, object]]:
    """Given a <node> Element, return a dict if it contains a tag k="name".

    Returned dict has keys: id, lat, lon, name, tags
    If the node has no name tag, return None.
    """
    tags: Dict[str, str] = {}
    name_value: Optional[str] = None

    for child in list(elem):
        if local_name(child.tag) == 'tag':
            k = child.get('k')
            v = child.get('v')
            if k is None:
                continue
            tags[k] = v
            if k == 'name':
                name_value = v

    if name_value is None:
        return None

    lat = elem.get('lat')
    lon = elem.get('lon')

    return {
        'id': elem.get('id'),
        'lat': float(lat) if lat is not None else None,
        'lon': float(lon) if lon is not None else None,
        'name': name_value,
        'tags': tags,
    }


def extract_named_nodes_from_iter(events: Iterable[Tuple[str, ET.Element]]) -> Generator[Dict[str, object], None, None]:
    """Yield dicts for each <node> element with a tag k="name".

    Input should be an iterable of (event, element) pairs as produced by
    xml.etree.ElementTree.iterparse(..., events=('end',)). Elements are
    cleared after processing to keep memory usage low when streaming.
    """
    for event, elem in events:
        if local_name(elem.tag) == 'node':
            obj = extract_named_node_obj(elem)
            if obj is not None:
                yield obj
            elem.clear()


def process_map_xml(input_path: str = 'map.xml', output_path: str = 'name_nodes.json', pretty: bool = True) -> int:
    """Process an XML file (e.g., map.xml), extract named nodes and write JSON output.

    Returns the number of nodes written.
    """
    events = ET.iterparse(input_path, events=('end',))
    written = 0
    with open(output_path, 'w', encoding='utf-8') as outf:
        outf.write('[')
        first = True
        for obj in extract_named_nodes_from_iter(events):
            if not first:
                outf.write(',\n')
            if pretty:
                outf.write(json.dumps(obj, ensure_ascii=False, indent=2))
            else:
                outf.write(json.dumps(obj, ensure_ascii=False))
            first = False
            written += 1
        outf.write(']\n')
    return written


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Process map XML and extract nodes with tag k="name" (defaults to map.xml)')
    p.add_argument('-i', '--input', default='/Users/admin/Desktop/6321PROJECT1/map.xml')
    p.add_argument('-o', '--output', default='/Users/admin/Desktop/6321PROJECT1/name_nodes.json')
    p.add_argument('--no-pretty', dest='pretty', action='store_false')
    args = p.parse_args()
    count = process_map_xml(args.input, args.output, pretty=args.pretty)
    print(f"Wrote {count} named node(s) to {args.output}")
