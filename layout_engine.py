"""
Рушій компонування сімейного дерева.
"""

import networkx as nx
from typing import Dict, Tuple, Set, List, Optional

# --- КОНСТАНТИ РОЗМІРІВ ---
REL_PARTNER = 'partner'
REL_CHILD = 'child'
NODE_WIDTH = 140
NODE_HEIGHT = 45
H_GAP = 30
V_GAP = 80
PARTNER_GAP = 8


class LayoutEngine:
    def __init__(self):
        self.node_width = NODE_WIDTH
        self.node_height = NODE_HEIGHT
        self.horizontal_gap = H_GAP
        self.vertical_gap = V_GAP
        self.partner_gap = PARTNER_GAP

    def calculate_layout(self, graph: nx.DiGraph, focus_node_id: str) -> Optional[Dict[str, Tuple[float, float]]]:
        if not graph or not graph.has_node(focus_node_id):
            return None

        try:
            generations = self._calculate_all_generations(graph, focus_node_id)
            if not generations:
                return {focus_node_id: (0, 0)}

            min_gen = min(generations.values())
            
            positions = {}
            visited = set()
            
            roots = self._find_effective_roots(graph)
            roots.sort(key=lambda r: 0 if self._is_connected_to(graph, r, focus_node_id, set()) else 1)
            
            current_x = 0.0
            
            for root_id in roots:
                if root_id in visited:
                    continue
                
                tree_pos, tree_width = self._layout_tree(
                    graph, root_id, generations, min_gen, visited, 0
                )
                
                for node_id, (x, y) in tree_pos.items():
                    positions[node_id] = (x + current_x, y)
                
                current_x += tree_width + self.node_width * 2

            # Тільки розв'язуємо колізії, без агресивної компактизації
            self._resolve_collisions(positions, generations)

            return positions

        except Exception as e:
            print(f"Layout error: {e}")
            import traceback
            traceback.print_exc()
            return {focus_node_id: (0, 0)}

    def _layout_tree(self, graph: nx.DiGraph, node_id: str,
                    generations: Dict, min_gen: int,
                    visited: Set[str], x_offset: float) -> Tuple[Dict[str, Tuple[float, float]], float]:
        """Розміщує дерево від вказаного вузла."""
        
        if node_id in visited:
            return {}, 0
        
        positions = {}
        gen = generations.get(node_id, 0)
        y = (gen - min_gen) * (self.node_height + self.vertical_gap)
        
        # Знаходимо партнерів того ж покоління
        partners = [p for p in self._get_partners(graph, node_id) 
                   if p not in visited and generations.get(p) == gen]
        
        # Сімейна одиниця
        family = [node_id] + partners
        for member in family:
            visited.add(member)
        
        # Збираємо всіх дітей сімейної одиниці
        all_children = set()
        for parent in family:
            all_children.update(self._get_children(graph, parent))
        
        children_list = sorted([c for c in all_children if c not in visited])
        
        family_width = len(family) * self.node_width + (len(family) - 1) * self.partner_gap
        
        if not children_list:
            # Листок - просто розміщуємо сім'ю
            curr_x = x_offset
            for member in family:
                positions[member] = (curr_x + self.node_width / 2, y)
                curr_x += self.node_width + self.partner_gap
            return positions, family_width
        
        # Рекурсивно розміщуємо дітей
        children_data = []
        child_x = x_offset
        total_children_width = 0
        
        for child_id in children_list:
            child_pos, child_width = self._layout_tree(
                graph, child_id, generations, min_gen, visited, child_x
            )
            
            if child_width > 0:
                positions.update(child_pos)
                
                # Центр дитячої сімейної одиниці
                child_center = self._get_subtree_center(child_id, child_pos, graph, generations)
                children_data.append((child_id, child_center, child_width))
                child_x += child_width + self.horizontal_gap
                total_children_width += child_width + self.horizontal_gap
        
        if total_children_width > 0:
            total_children_width -= self.horizontal_gap
        
        # Центруємо батьків над дітьми
        if children_data:
            leftmost = children_data[0][1]
            rightmost = children_data[-1][1]
            children_center = (leftmost + rightmost) / 2
            
            family_start_x = children_center - family_width / 2
            
            curr_x = family_start_x
            for member in family:
                positions[member] = (curr_x + self.node_width / 2, y)
                curr_x += self.node_width + self.partner_gap
        else:
            curr_x = x_offset
            for member in family:
                positions[member] = (curr_x + self.node_width / 2, y)
                curr_x += self.node_width + self.partner_gap
        
        return positions, max(family_width, total_children_width)

    def _get_subtree_center(self, node_id: str, positions: Dict, 
                           graph: nx.DiGraph, generations: Dict) -> float:
        """Повертає центр сімейної одиниці вузла."""
        if node_id not in positions:
            return 0
        
        gen = generations.get(node_id, 0)
        family_x = [positions[node_id][0]]
        
        # Додаємо партнерів того ж покоління
        for p in self._get_partners(graph, node_id):
            if p in positions and generations.get(p) == gen:
                family_x.append(positions[p][0])
        
        return (min(family_x) + max(family_x)) / 2

    def _resolve_collisions(self, positions: Dict, generations: Dict):
        """Розсуває вузли що перекриваються."""
        by_gen = {}
        for node_id, (x, y) in positions.items():
            gen = generations.get(node_id, 0)
            if gen not in by_gen:
                by_gen[gen] = []
            by_gen[gen].append(node_id)
        
        for gen in by_gen:
            nodes = sorted(by_gen[gen], key=lambda n: positions[n][0])
            
            for i in range(len(nodes) - 1):
                n1 = nodes[i]
                n2 = nodes[i + 1]
                
                x1 = positions[n1][0]
                x2 = positions[n2][0]
                
                min_dist = self.node_width + self.partner_gap
                
                if x2 - x1 < min_dist:
                    push = min_dist - (x2 - x1) + 2
                    for j in range(i + 1, len(nodes)):
                        nj = nodes[j]
                        px, py = positions[nj]
                        positions[nj] = (px + push, py)

    def _is_connected_to(self, graph: nx.DiGraph, start: str, 
                        target: str, visited: Set[str]) -> bool:
        if start == target:
            return True
        if start in visited:
            return False
        visited.add(start)
        
        for child in self._get_children(graph, start):
            if self._is_connected_to(graph, child, target, visited):
                return True
        for partner in self._get_partners(graph, start):
            if self._is_connected_to(graph, partner, target, visited):
                return True
        return False

    def _find_effective_roots(self, graph: nx.DiGraph) -> List[str]:
        roots = []
        for n in graph.nodes():
            p = self._get_parents(graph, n)
            if not p[0] and not p[1]:
                roots.append(n)
        return roots

    def _get_parents(self, graph, n):
        d = graph.nodes.get(n, {})
        return (d.get('father'), d.get('mother'))

    def _get_partners(self, graph, n):
        partners = set()
        for u, v, a in graph.edges(n, data=True):
            if a.get('type') == REL_PARTNER:
                partners.add(v)
        for c in self._get_children(graph, n):
            p = self._get_parents(graph, c)
            if p[0] and p[0] != n:
                partners.add(p[0])
            if p[1] and p[1] != n:
                partners.add(p[1])
        return list(partners)

    def _get_children(self, graph, n):
        return [v for u, v, a in graph.edges(n, data=True) if a.get('type') == REL_CHILD]

    def _calculate_all_generations(self, graph: nx.DiGraph, focus_id: str) -> Dict[str, int]:
        gens = {focus_id: 0}
        q = [(focus_id, 0)]
        visited = {focus_id}

        while q:
            curr, g = q.pop(0)

            for p in [x for x in self._get_parents(graph, curr) if x]:
                if p not in gens:
                    gens[p] = g - 1
                    visited.add(p)
                    q.append((p, g - 1))

            for c in self._get_children(graph, curr):
                if c not in gens:
                    gens[c] = g + 1
                    visited.add(c)
                    q.append((c, g + 1))

            for p in self._get_partners(graph, curr):
                if p not in gens:
                    gens[p] = g
                    visited.add(p)
                    q.append((p, g))

        for n in graph.nodes():
            if n not in gens:
                gens[n] = 0
        return gens