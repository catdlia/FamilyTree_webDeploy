import unittest
import os
import networkx as nx
import shutil
from data_manager import DataManager
from layout_engine import LayoutEngine


class TestFamilyTreeIntegrity(unittest.TestCase):

    def setUp(self):
        # Видаляємо старі тестові файли перед кожним тестом
        if os.path.exists("test_project.tree"):
            os.remove("test_project.tree")
        shutil.rmtree("1_Тестова_Людина", ignore_errors=True)

    def test_1_data_manager_save_load_cycle(self):
        print("\n--- ЗАПУСК ТЕСТУ №1: DataManager Save/Load Cycle ---")
        test_file = "test_project.tree"
        test_person_name = "Тестова Людина"

        dm_save = DataManager()
        dm_save.load_project(test_file)  # Налаштовуємо шлях для збереження
        person_id = dm_save.add_person(test_person_name)
        dm_save.save_project()  # ВИПРАВЛЕНО: Викликаємо без аргументів

        self.assertTrue(os.path.exists(test_file))

        dm_load = DataManager()
        self.assertTrue(dm_load.load_project(test_file))
        self.assertIn(person_id, dm_load.graph.nodes)
        self.assertEqual(dm_load.graph.nodes[person_id]['label'], test_person_name)
        print("--- ТЕСТ №1 УСПІШНИЙ ---")

    def test_2_layout_engine_returns_positions(self):
        print("\n--- ЗАПУСК ТЕСТУ №2: LayoutEngine returns positions ---")
        test_graph = nx.DiGraph()
        test_graph.add_node("1", label="Адам")
        test_graph.add_node("2", label="Єва")
        test_graph.add_edge("1", "2")

        engine = LayoutEngine()
        positions = engine.calculate_layout(test_graph, "1")

        self.assertIsNotNone(positions)
        self.assertIn("1", positions)
        self.assertIn("2", positions)
        print("--- ТЕСТ №2 УСПІШНИЙ ---")


if __name__ == '__main__':
    unittest.main()