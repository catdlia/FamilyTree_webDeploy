"""
Рендерер SVG для веб-версії сімейного дерева.
Перетворює граф та координати LayoutEngine у інтерактивний SVG рядок.
"""

import networkx as nx
from collections import defaultdict
# Переконайся, що layout_engine.py існує і містить ці константи
from layout_engine import NODE_WIDTH, NODE_HEIGHT
from relationship_calculator import RelationshipCalculator

# Стилі для SVG
STYLE = """
<style>
    .node-rect { cursor: pointer; transition: all 0.2s; }
    .node-rect:hover { stroke-width: 3; filter: drop-shadow(0px 0px 5px rgba(255, 215, 0, 0.5)); }
    .node-text { pointer-events: none; font-family: sans-serif; font-size: 12px; }
    .id-text { font-size: 8px; fill: #666; }
</style>
"""

class SVGRenderer:
    def __init__(self, graph: nx.DiGraph, positions: dict, focus_id: str):
        self.graph = graph
        self.positions = positions
        self.focus_id = focus_id
        self.rel_calc = RelationshipCalculator(graph)

        # Обчислюємо межі для viewBox
        xs = [pos[0] for pos in positions.values()]
        ys = [pos[1] for pos in positions.values()]

        if xs and ys:
            self.min_x = min(xs) - NODE_WIDTH
            self.min_y = min(ys) - NODE_HEIGHT
            self.width = max(xs) - self.min_x + NODE_WIDTH
            self.height = max(ys) - self.min_y + NODE_HEIGHT
        else:
            self.min_x, self.min_y, self.width, self.height = 0, 0, 800, 600

    def generate_svg(self, zoom_level: float = 1.0) -> str:
        elements = []

        # 1. Лінії зв'язків (Edges)
        elements.extend(self._draw_edges())

        # 2. Вузли (Nodes)
        elements.extend(self._draw_nodes())

        # 3. РОЗРАХУНОК МАСШТАБУ
        # viewBox залишається незмінним (це наші логічні координати)
        # А width/height ми множимо на zoom_level (це фізичні пікселі на екрані)

        final_width = int(self.width * zoom_level)
        final_height = int(self.height * zoom_level)

        # Збираємо все в один SVG
        # ВАЖЛИВО: Ми явно вказуємо width і height у пікселях
        svg_content = f"""
        <svg viewBox="{self.min_x} {self.min_y} {self.width} {self.height}" 
             width="{final_width}px" 
             height="{final_height}px" 
             preserveAspectRatio="xMidYMid meet"
             xmlns="http://www.w3.org/2000/svg">
            {STYLE}
            <defs>
                <marker id="arrow" markerWidth="10" markerHeight="10" refX="10" refY="3" orient="auto" markerUnits="strokeWidth">
                  <path d="M0,0 L0,6 L9,3 z" fill="#87CEEB" />
                </marker>
            </defs>
            {''.join(elements)}
        </svg>
        """
        return svg_content

    def _draw_nodes(self) -> list:
        nodes_svg = []

        for node_id, (x, y) in self.positions.items():
            data = self.graph.nodes[node_id]
            label = data.get('label', 'Unknown')

            # Отримуємо кольори через калькулятор (він повертає HEX)
            fill_hex, border_hex, stroke_w = self.rel_calc.get_node_color(self.focus_id, node_id)

            # Координати для rect (центровані)
            rect_x = x - NODE_WIDTH / 2
            rect_y = y - NODE_HEIGHT / 2

            # Обрізання довгого тексту
            display_label = label[:16] + "..." if len(label) > 18 else label

            # Формуємо групу з посиланням (для click-detector)
            # Важливо: id в тезі <a> - це те, що поверне детектор
            node_html = f"""
            <a href='#' id='{node_id}'>
                <g>
                    <rect x="{rect_x}" y="{rect_y}" width="{NODE_WIDTH}" height="{NODE_HEIGHT}" 
                          rx="5" ry="5" fill="{fill_hex}" stroke="{border_hex}" stroke-width="{stroke_w}" class="node-rect" />
                    <text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="middle" fill="black" class="node-text">
                        {display_label}
                    </text>
                    <text x="{x}" y="{y + 12}" text-anchor="middle" class="node-text id-text">
                        ID: {node_id}
                    </text>
                </g>
            </a>
            """
            nodes_svg.append(node_html)

        return nodes_svg

    def _draw_edges(self) -> list:
        edges_svg = []

        # Логіка групування дітей
        child_to_parents = defaultdict(set)
        for child_id in self.graph.nodes():
            node_data = self.graph.nodes[child_id]
            if node_data.get('father'): child_to_parents[child_id].add(node_data['father'])
            if node_data.get('mother'): child_to_parents[child_id].add(node_data['mother'])

        # Додаємо зв'язки з графа (якщо є edges типу 'child')
        for u, v, attrs in self.graph.edges(data=True):
            if attrs.get('type') == 'child':
                child_to_parents[v].add(u)

        family_children = defaultdict(list)
        for child_id, parents_set in child_to_parents.items():
            if child_id not in self.positions: continue
            parents_in_pos = [p for p in parents_set if p in self.positions]
            if parents_in_pos:
                parents_key = tuple(sorted(parents_in_pos))
                family_children[parents_key].append(child_id)

        # Малюємо ортогональні лінії
        for parents_key, children in family_children.items():
            if not children: continue
            parents = list(parents_key)

            # Колір лінії
            edge_color = self.rel_calc.get_edge_color(self.focus_id, parents[0], children[0])

            # 1. Центр батьків
            if len(parents) >= 2:
                p1 = self.positions[parents[0]]
                p2 = self.positions[parents[1]]
                parent_center_x = (p1[0] + p2[0]) / 2
                parent_bottom_y = max(p1[1], p2[1]) + NODE_HEIGHT / 2
            else:
                p = self.positions[parents[0]]
                parent_center_x = p[0]
                parent_bottom_y = p[1] + NODE_HEIGHT / 2

            # 2. Розрахунок Y для гілки
            children_top_y = min(self.positions[c][1] for c in children) - NODE_HEIGHT / 2
            branch_y = parent_bottom_y + (children_top_y - parent_bottom_y) * 0.5

            # 3. Вертикальна лінія від батьків вниз
            edges_svg.append(self._line(parent_center_x, parent_bottom_y, parent_center_x, branch_y, edge_color))

            # 4. Горизонтальна лінія над дітьми
            children_x = [self.positions[c][0] for c in children]
            min_cx, max_cx = min(children_x), max(children_x)

            line_start_x = min(min_cx, parent_center_x)
            line_end_x = max(max_cx, parent_center_x)

            if abs(line_end_x - line_start_x) > 1:
                edges_svg.append(self._line(line_start_x, branch_y, line_end_x, branch_y, edge_color))

            # 5. Вертикальні лінії до кожного з дітей
            for child_id in children:
                cx, cy = self.positions[child_id]
                child_top_y = cy - NODE_HEIGHT / 2
                edges_svg.append(self._line(cx, branch_y, cx, child_top_y, edge_color))

        return edges_svg

    def _line(self, x1, y1, x2, y2, color):
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2" />'