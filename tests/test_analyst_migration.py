import unittest

from src.utils.analyst_migration import LEGACY_TO_CURRENT, migrate_flow, migrate_graph


class AnalystMigrationTests(unittest.TestCase):
    def test_all_retired_analysts_have_distinct_replacements(self):
        self.assertEqual(len(LEGACY_TO_CURRENT), 12)
        self.assertEqual(len(set(LEGACY_TO_CURRENT.values())), 12)

    def test_saved_flow_preserves_topology_and_configuration(self):
        old_id = "ben_graham_abc123"
        new_id = "deng_xiaofeng_abc123"
        nodes = [
            {"id": "stock-analyzer-node_123abc", "type": "stock-analyzer-node", "data": {"tickers": "600519"}},
            {"id": old_id, "type": "agent-node", "position": {"x": 400, "y": 0},
             "data": {"name": "Ben Graham", "internal_state": {"model": "test-model"}}},
            {"id": "portfolio_manager_123abc", "type": "portfolio-manager-node"},
        ]
        edges = [
            {"id": f"stock-analyzer-node_123abc-{old_id}", "source": "stock-analyzer-node_123abc", "target": old_id},
            {"id": f"{old_id}-portfolio_manager_123abc", "source": old_id, "target": "portfolio_manager_123abc"},
        ]
        data = {"nodeStates": {old_id: {"model": "test-model"}},
                "nodeContextData": {old_id: {"reasoning": "old analysis"}}}
        migrated_nodes, migrated_edges, migrated_data, changed = migrate_flow(nodes, edges, data)

        self.assertTrue(changed)
        self.assertEqual(migrated_nodes[1]["id"], new_id)
        self.assertEqual(migrated_nodes[1]["data"]["name"], "邓晓峰")
        self.assertEqual(migrated_nodes[1]["position"], {"x": 400, "y": 0})
        self.assertEqual(migrated_nodes[1]["data"]["internal_state"], {"model": "test-model"})
        self.assertEqual(migrated_edges[0]["target"], new_id)
        self.assertEqual(migrated_edges[1]["source"], new_id)
        self.assertIn(new_id, migrated_data["nodeStates"])
        self.assertNotIn("nodeContextData", migrated_data)
        self.assertIn(old_id, migrated_data["legacyNodeContextData"])
        self.assertEqual(nodes[1]["id"], old_id)  # Input is not mutated.
        self.assertFalse(migrate_flow(migrated_nodes, migrated_edges, migrated_data)[3])

    def test_request_graph_rewrites_only_known_agent_ids(self):
        nodes, edges, id_map = migrate_graph(
            [{"id": "warren_buffett_xyz789"}, {"id": "portfolio_manager_abc123"}],
            [{"id": "edge-1", "source": "warren_buffett_xyz789", "target": "portfolio_manager_abc123"}],
        )
        self.assertEqual(id_map, {"warren_buffett_xyz789": "lin_yuan_xyz789"})
        self.assertEqual(edges[0]["source"], "lin_yuan_xyz789")
        self.assertEqual(nodes[1]["id"], "portfolio_manager_abc123")

    def test_older_composite_state_keys_and_exact_ids(self):
        nodes, _, data, changed = migrate_flow(
            [{"id": "ben_graham", "data": {"name": "Ben Graham"}}],
            [], {"nodeStates": {"12:ben_graham": {"model": "local"}}},
        )
        self.assertTrue(changed)
        self.assertEqual(nodes[0]["id"], "deng_xiaofeng")
        self.assertEqual(nodes[0]["data"]["name"], "邓晓峰")
        self.assertIn("12:deng_xiaofeng", data["nodeStates"])

    def test_collision_is_rejected_without_changing_input(self):
        nodes = [{"id": "ben_graham_abc123"}, {"id": "deng_xiaofeng_abc123"}]
        with self.assertRaisesRegex(ValueError, "duplicate node IDs"):
            migrate_graph(nodes, [])
        self.assertEqual(nodes[0]["id"], "ben_graham_abc123")


if __name__ == "__main__":
    unittest.main()
