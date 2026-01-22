"""
Рушій обчислення родинних зв'язків.
Визначає покоління, ступінь спорідненості та тип зв'язку між будь-якими двома людьми.
Версія: Pure Python (без PySide6).
"""

import networkx as nx
from typing import Tuple, Dict, Set

class RelationshipCalculator:
    """
    Обчислює родинні зв'язки між людьми у сімейному дереві.
    """

    def __init__(self, graph: nx.DiGraph):
        self.graph = graph
        self.generation_cache = {}
        self.relationship_cache = {}

    def clear_cache(self):
        """Очищає кеш при зміні графу."""
        self.generation_cache.clear()
        self.relationship_cache.clear()

    # ==================== БАЗОВІ ОБЧИСЛЕННЯ ====================

    def get_generation_level(self, focus_id: str, person_id: str) -> int:
        """
        Обчислює різницю поколінь.
        """
        cache_key = (focus_id, person_id)
        if cache_key in self.generation_cache:
            return self.generation_cache[cache_key]

        focus_ancestors = self._get_all_ancestors_with_depth(focus_id)
        person_ancestors = self._get_all_ancestors_with_depth(person_id)

        if person_id in focus_ancestors:
            result = -focus_ancestors[person_id]
            self.generation_cache[cache_key] = result
            return result

        if focus_id in person_ancestors:
            result = person_ancestors[focus_id]
            self.generation_cache[cache_key] = result
            return result

        common_ancestors = set(focus_ancestors.keys()) & set(person_ancestors.keys())

        if not common_ancestors:
            self.generation_cache[cache_key] = 999
            return 999

        min_distance = float('inf')
        closest_ancestor = None
        for ancestor in common_ancestors:
            total_distance = focus_ancestors[ancestor] + person_ancestors[ancestor]
            if total_distance < min_distance:
                min_distance = total_distance
                closest_ancestor = ancestor

        generation_diff = person_ancestors[closest_ancestor] - focus_ancestors[closest_ancestor]
        self.generation_cache[cache_key] = generation_diff
        return generation_diff

    def _get_all_ancestors_with_depth(self, person_id: str) -> Dict[str, int]:
        ancestors = {}
        queue = [(person_id, 0)]
        visited = set()

        while queue:
            current_id, depth = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            if current_id != person_id:
                ancestors[current_id] = depth

            person_data = self.graph.nodes.get(current_id, {})
            father_id = person_data.get('father')
            mother_id = person_data.get('mother')

            if father_id and self.graph.has_node(father_id):
                queue.append((father_id, depth + 1))
            if mother_id and self.graph.has_node(mother_id):
                queue.append((mother_id, depth + 1))

        return ancestors

    def get_degree_of_relationship(self, focus_id: str, person_id: str) -> int:
        if focus_id == person_id:
            return 0

        focus_ancestors = self._get_all_ancestors_with_depth(focus_id)
        person_ancestors = self._get_all_ancestors_with_depth(person_id)

        if person_id in focus_ancestors:
            return focus_ancestors[person_id]
        if focus_id in person_ancestors:
            return person_ancestors[focus_id]

        common_ancestors = set(focus_ancestors.keys()) & set(person_ancestors.keys())
        if not common_ancestors:
            return 999

        min_degree = float('inf')
        for ancestor in common_ancestors:
            degree = focus_ancestors[ancestor] + person_ancestors[ancestor]
            if degree < min_degree:
                min_degree = degree
        return min_degree

    def get_siblings(self, person_id: str) -> Set[str]:
        person_data = self.graph.nodes.get(person_id, {})
        father_id = person_data.get('father')
        mother_id = person_data.get('mother')
        siblings = set()

        if not father_id and not mother_id:
            return siblings

        for node_id, node_data in self.graph.nodes(data=True):
            if node_id == person_id:
                continue
            node_father = node_data.get('father')
            node_mother = node_data.get('mother')

            if father_id and mother_id:
                if node_father == father_id and node_mother == mother_id:
                    siblings.add(node_id)
            elif father_id and node_father == father_id:
                siblings.add(node_id)
            elif mother_id and node_mother == mother_id:
                siblings.add(node_id)
        return siblings

    def get_partners(self, person_id: str) -> Set[str]:
        partners = set()
        for u, v, attrs in self.graph.edges(person_id, data=True):
            if attrs.get('type') == 'partner':
                partners.add(v)

        person_children = set()
        for node_id, node_data in self.graph.nodes(data=True):
            if node_data.get('father') == person_id or node_data.get('mother') == person_id:
                person_children.add(node_id)

        for child_id in person_children:
            child_data = self.graph.nodes[child_id]
            father = child_data.get('father')
            mother = child_data.get('mother')
            if father and father != person_id:
                partners.add(father)
            if mother and mother != person_id:
                partners.add(mother)
        return partners

    def get_children(self, person_id: str) -> Set[str]:
        children = set()
        for node_id, node_data in self.graph.nodes(data=True):
            if node_data.get('father') == person_id or node_data.get('mother') == person_id:
                children.add(node_id)
        return children

    def get_relationship_type(self, focus_id: str, person_id: str) -> Tuple[str, str]:
        if focus_id == person_id:
            return ('self', 'Я')

        cache_key = (focus_id, person_id)
        if cache_key in self.relationship_cache:
            return self.relationship_cache[cache_key]

        generation = self.get_generation_level(focus_id, person_id)
        degree = self.get_degree_of_relationship(focus_id, person_id)

        result = self._determine_relationship(focus_id, person_id, generation, degree)
        self.relationship_cache[cache_key] = result
        return result

    def _determine_relationship(self, focus_id: str, person_id: str,
                                generation: int, degree: int) -> Tuple[str, str]:
        if person_id in self.get_partners(focus_id):
            return ('partner', 'Партнер/Дружина')

        if generation < 0:
            if degree == 1:
                focus_data = self.graph.nodes[focus_id]
                if focus_data.get('father') == person_id:
                    return ('parent', 'Батько')
                elif focus_data.get('mother') == person_id:
                    return ('parent', 'Мати')
                return ('parent', 'Батько/Мати')
            elif degree == 2: return ('parent', 'Дідусь/Бабуся')
            elif degree == 3: return ('parent', 'Прадід/Прабабуся')
            elif degree == 4: return ('parent', 'Прапрадід/Прапрабабуся')
            elif degree <= 10:
                return ('parent', f'Пра({degree - 2})дід/бабуся')
            else:
                return ('distant', 'Не визначено')

        if generation > 0:
            if degree == 1: return ('child', 'Син/Дочка')
            elif degree == 2: return ('child', 'Онук/Онука')
            elif degree == 3: return ('child', 'Правнук/Правнучка')
            elif degree == 4: return ('child', 'Праправнук/Праправнучка')
            elif degree <= 10:
                return ('child', f'Пра({degree - 2})внук/внучка')
            else:
                return ('distant', 'Не визначено')

        if generation == 0:
            if person_id in self.get_siblings(focus_id):
                if degree == 2: return ('sibling', 'Брат/Сестра')
            if degree == 4: return ('sibling', 'Двоюрідний брат/сестра')
            if degree == 6: return ('sibling', 'Троюрідний брат/сестра')
            if degree > 6 and degree <= 12 and degree % 2 == 0:
                return ('sibling', f'{(degree // 2) - 1}-юрідний брат/сестра')
            if degree > 12: return ('distant', 'Не визначено')

        if generation == -1 and degree == 3: return ('extended', 'Дядько/Тітка')
        if generation == -1 and degree > 3 and degree <= 10:
            n = (degree - 2) // 2
            return ('extended', f'{n}-юрідний дядько/тітка' if n > 2 else 'Двоюрідний дядько/тітка')

        if generation == 1 and degree == 3: return ('extended', 'Племінник/Племінниця')
        if generation == 1 and degree > 3 and degree <= 10:
            n = (degree - 2) // 2
            return ('extended', f'{n}-юрідний племінник/племінниця' if n > 2 else 'Двоюрідний племінник/племінниця')

        if degree < 15:
            return ('distant', f'Родич ({degree}° спорідненості)')
        return ('distant', 'Не визначено (не пов\'язані)')

    # ==================== КОЛЬОРОВЕ КОДУВАННЯ (HEX) ====================

    def _rgb_to_hex(self, r, g, b):
        return f"#{r:02x}{g:02x}{b:02x}"

    def get_node_color(self, focus_id: str, person_id: str) -> Tuple[str, str, int]:
        """Повертає кольори вузла у форматі HEX string."""
        category, detailed_name = self.get_relationship_type(focus_id, person_id)
        degree = self.get_degree_of_relationship(focus_id, person_id)

        if category == 'self':
            return ("#FFD700", "#000000", 3)

        elif category == 'parent':
            if degree == 1: return ("#87CEEB", "#4169E1", 2)
            elif degree == 2: return ("#B0E0E6", "#5F9EA0", 2)
            else:
                intensity = max(135, 200 - degree * 10)
                return (self._rgb_to_hex(intensity, 206, 235), "#778899", 1)

        elif category == 'child':
            if degree == 1: return ("#98FB98", "#228B22", 2)
            elif degree == 2: return ("#90EE90", "#32CD32", 2)
            else:
                intensity = max(144, 250 - degree * 15)
                return (self._rgb_to_hex(intensity, 238, intensity), "#6B8E23", 1)

        elif category == 'partner':
            return ("#FFB6C1", "#FF1493", 2)

        elif category == 'sibling':
            if degree == 2: return ("#DDA0DD", "#8B008B", 2)
            elif degree == 4: return ("#D8BFD8", "#9370DB", 2)
            else: return ("#E6E6FA", "#9932CC", 1)

        elif category == 'extended':
            if degree <= 3: return ("#FFD700", "#FF8C00", 2)
            else: return ("#FFDAB9", "#CD853F", 1)

        else:  # distant
            if "не пов'язані" in detailed_name.lower() or degree >= 15:
                return ("#808080", "#FF0000", 2)
            elif degree < 999:
                intensity = max(200, 255 - degree * 5)
                return (self._rgb_to_hex(intensity, intensity, intensity), "#696969", 1)
            else:
                return ("#D3D3D3", "#A9A9A9", 1)

    def get_edge_color(self, focus_id: str, source_id: str, target_id: str) -> str:
        """Повертає колір ребра у форматі HEX."""
        source_category, _ = self.get_relationship_type(focus_id, source_id)
        target_category, _ = self.get_relationship_type(focus_id, target_id)

        if source_id == focus_id or target_id == focus_id:
            target_cat = target_category if source_id == focus_id else source_category
            if target_cat == 'parent': return "#4169E1"
            elif target_cat == 'child': return "#228B22"
            elif target_cat == 'partner': return "#FF1493"
            elif target_cat == 'sibling': return "#8B008B"
            elif target_cat == 'extended': return "#FF8C00"
            else: return "#9696B4" # Сірий

        if source_category == 'parent' and target_category == 'parent': return "#FF1493"
        if (source_category == 'parent' and target_category == 'child') or \
           (source_category == 'child' and target_category == 'parent'): return "#4169E1"
        if source_category == 'sibling' and target_category == 'sibling': return "#8B008B"
        if source_category == 'child' and target_category == 'child': return "#228B22"
        if source_category == 'partner' or target_category == 'partner': return "#FF1493"
        if source_category == 'extended' or target_category == 'extended': return "#FF8C00"

        return "#9696B4" # Сірий