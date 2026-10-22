"""Upgrade saved analyst graphs to the A-share investor node IDs.

The mapping is a mechanical replacement of the twelve retired slots. It does
not claim that the new investor has the same method as the old one.
"""

from __future__ import annotations

from copy import deepcopy


LEGACY_TO_CURRENT = {
    "aswath_damodaran": "duan_yongping",
    "ben_graham": "deng_xiaofeng",
    "bill_ackman": "feng_liu",
    "cathie_wood": "fu_pengbo",
    "charlie_munger": "zhu_shaoxing",
    "michael_burry": "zhang_kun",
    "mohnish_pabrai": "liu_yanchun",
    "peter_lynch": "xie_zhiyu",
    "phil_fisher": "dong_chengfei",
    "rakesh_jhunjhunwala": "wang_yawei",
    "stanley_druckenmiller": "chen_guangming",
    "warren_buffett": "lin_yuan",
}

CURRENT_NAMES = {
    "duan_yongping": "段永平",
    "deng_xiaofeng": "邓晓峰",
    "feng_liu": "冯柳",
    "fu_pengbo": "傅鹏博",
    "zhu_shaoxing": "朱少醒",
    "zhang_kun": "张坤",
    "liu_yanchun": "刘彦春",
    "xie_zhiyu": "谢治宇",
    "dong_chengfei": "董承非",
    "wang_yawei": "王亚伟",
    "chen_guangming": "陈光明",
    "lin_yuan": "林园",
}


def current_node_id(node_id: str) -> str:
    """Keep a node's unique suffix while replacing a retired analyst key."""
    for old_key, new_key in LEGACY_TO_CURRENT.items():
        if node_id == old_key:
            return new_key
        if node_id.startswith(old_key + "_"):
            suffix = node_id[len(old_key):]
            if suffix == "_agent" or (len(suffix) == 7 and suffix[1:].isalnum()):
                return new_key + suffix
    return node_id


def _mapped_state_key(key: str, id_map: dict[str, str]) -> str:
    if key in id_map:
        return id_map[key]
    if ":" in key:
        prefix, node_id = key.rsplit(":", 1)
        if node_id in id_map:
            return f"{prefix}:{id_map[node_id]}"
    return key


def migrate_graph(nodes: list[dict], edges: list[dict]) -> tuple[list[dict], list[dict], dict[str, str]]:
    id_map = {
        node["id"]: current_node_id(node["id"])
        for node in nodes if isinstance(node, dict) and isinstance(node.get("id"), str)
        and current_node_id(node["id"]) != node["id"]
    }
    if not id_map:
        return nodes, edges, {}
    if len({id_map.get(node.get("id"), node.get("id")) for node in nodes}) != len(nodes):
        raise ValueError("Legacy analyst migration would create duplicate node IDs")

    migrated_nodes = deepcopy(nodes)
    for node in migrated_nodes:
        old_id = node.get("id")
        if old_id not in id_map:
            continue
        node["id"] = id_map[old_id]
        key = next(new for old, new in LEGACY_TO_CURRENT.items()
                   if old_id == old or old_id.startswith(old + "_"))
        if key in CURRENT_NAMES:
            node["data"] = {**(node.get("data") or {}),
                            "name": CURRENT_NAMES[key],
                            "description": "A股投资理念启发的策略原型，并非本人观点。",
                            "status": "Idle"}

    migrated_edges = deepcopy(edges)
    for edge in migrated_edges:
        edge["source"] = id_map.get(edge.get("source"), edge.get("source"))
        edge["target"] = id_map.get(edge.get("target"), edge.get("target"))
        if isinstance(edge.get("id"), str):
            for old_id, new_id in sorted(id_map.items(), key=lambda item: len(item[0]), reverse=True):
                edge["id"] = edge["id"].replace(old_id, new_id)
    return migrated_nodes, migrated_edges, id_map


def migrate_flow(nodes: list[dict], edges: list[dict], data: dict | None):
    migrated_nodes, migrated_edges, id_map = migrate_graph(nodes, edges)
    if not id_map:
        return nodes, edges, data, False

    migrated_data = deepcopy(data) if isinstance(data, dict) else {}
    states = migrated_data.get("nodeStates")
    if isinstance(states, dict):
        migrated_data["nodeStates"] = {_mapped_state_key(key, id_map): value for key, value in states.items()}
    elif not any(key in migrated_data for key in ("nodeStates", "nodeContextData")):
        # Older saves stored node states directly in the data object.
        migrated_data = {_mapped_state_key(key, id_map): value for key, value in migrated_data.items()}

    # Saved runtime output belongs to the retired analysts. Keep it for audit,
    # but never present it as if the replacement analysts produced it.
    if "nodeContextData" in migrated_data:
        migrated_data["legacyNodeContextData"] = migrated_data.pop("nodeContextData")
    migrated_data["analystMigrationV1"] = {"nodeIdMap": id_map}
    return migrated_nodes, migrated_edges, migrated_data, True
