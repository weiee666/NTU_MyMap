import json
import re

input = '/Users/admin/Desktop/6321PROJECT1/mapFromMzaeMap.json'
output = '/Users/admin/Desktop/6321PROJECT1/buildings.json'


with open(input, 'r', encoding='utf-8') as f:
    data = json.load(f)
results = []
for each in data["buildings"]:
    name = each["name"]
    id = each["id"]
    campusId = each["campusId"]
    # print(f"name: {name}, id: {id}, campusId: {campusId}")
    results.append({
        "name": name,
        "id": id,
        "campusId": campusId
    })
with open(output, 'w', encoding='utf-8') as outf:
    json.dump(results, outf, ensure_ascii=False, indent=2)

print(f"成功提取{len(results)}条记录到{output}")
