# Context for LLM

### Project Structure:
```text
./
    svg_renderer.py
    layout_engine.py
    streamlit_app.py
    run_tests.py
    tree_view.py
    data_manager.py
    relationship_calculator.py
    utils/
        auth_drive.py
        hasher.py
        logger_service.py
        security_utils.py
        persistence_service.py
    .streamlit/
    family_tree_data/
        1_Adam/
        8_4321/
        5_Seth/
        2_Eve/
        4_Abel/
        3_Cain/
        7_1 2/
```

### File Contents:

**File: `svg_renderer.py`**
```python
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

    def generate_svg(self) -> str:
        elements = []

        # 1. Лінії зв'язків (Edges)
        elements.extend(self._draw_edges())

        # 2. Вузли (Nodes)
        elements.extend(self._draw_nodes())

        # Збираємо все в один SVG
        svg_content = f"""
        <svg viewBox="{self.min_x} {self.min_y} {self.width} {self.height}" 
             width="100%" height="600" xmlns="http://www.w3.org/2000/svg">
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
```

**File: `layout_engine.py`**
```python
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
```

**File: `streamlit_app.py`**
```python
"""
Family Tree Editor - Secure Web Application
Візуалізація: Custom SVG Renderer (Orthogonal).
Функціонал: Read-Only Mode, Visual Linking, File Management, Cloud Sync & Logging.
Безпека: st.secrets + Session Management.
Мова: Українська.
"""

import streamlit as st
import streamlit_authenticator as stauth
import os
import base64
import re
import datetime
from st_click_detector import click_detector

# Імпорт локальних модулів
from data_manager import DataManager
from layout_engine import LayoutEngine
from svg_renderer import SVGRenderer
from relationship_calculator import RelationshipCalculator
from utils.security_utils import check_session_timeout, brute_force_protection
from utils.persistence_service import PersistenceService

# --- КОНФІГУРАЦІЯ СТОРІНКИ ---
st.set_page_config(
    page_title="Редактор Сімейного Дерева",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 1. ЛОГІКА ДАНИХ ТА СИНХРОНІЗАЦІЯ ---
@st.cache_resource
def get_persistence_service():
    """Створює сервіс синхронізації один раз."""
    return PersistenceService()

@st.cache_resource
def get_data_manager():
    # 1. Пробуємо синхронізувати з хмари при холодному старті
    ps = get_persistence_service()
    if not os.path.exists("family_tree_data"):
        # Якщо папки немає локально, пробуємо стягнути з Drive
        ps.download_latest_backup()

    # 2. Ініціалізуємо DataManager
    dm = DataManager()
    data_dir = "family_tree_data"
    data_file = os.path.join(data_dir, "family.tree")

    if not os.path.exists(data_dir): os.makedirs(data_dir)
    if os.path.exists(data_file): dm.load_project(data_file)
    else:
        dm.project_file_path = os.path.abspath(data_file)
        dm.project_directory = os.path.dirname(dm.project_file_path)
    return dm

def perform_backup(manual=False):
    """Виконує бекап з перевіркою часу."""
    BACKUP_INTERVAL_MIN = 10
    now = datetime.datetime.now()
    last_backup = st.session_state.get('last_backup_time')

    should_backup = False

    if manual:
        should_backup = True
    elif last_backup is None:
        should_backup = True
    else:
        diff = (now - last_backup).total_seconds() / 60
        if diff > BACKUP_INTERVAL_MIN:
            should_backup = True

    if should_backup:
        ps = get_persistence_service()

        # Явна перевірка для ручного режиму
        if manual and (not ps.is_enabled):
            st.sidebar.error(f"Налаштування хмари неповні: {ps.status}")
            return

        if ps.is_enabled:
            with st.spinner("💾 Створення бекапу на Google Drive..."):
                if ps.upload_backup():
                    st.session_state['last_backup_time'] = now
                    if manual:
                        # ВИПРАВЛЕНО: icon="cloud" -> icon="☁️"
                        st.toast("✅ Бекап успішно створено!", icon="☁️")
                    else:
                        print(f"Auto-backup created at {now}")
                else:
                    if manual: st.sidebar.error("Помилка завантаження (див. консоль).")
    elif manual:
        st.sidebar.info(f"Бекап вже був створений нещодавно (чекайте {BACKUP_INTERVAL_MIN} хв або перезавантажте).")

def save_state(dm):
    """Зберігає локально і тригерить авто-бекап."""
    dm.save_project()
    # Автоматичний бекап
    perform_backup(manual=False)
    st.cache_resource.clear()
    st.rerun()

# --- ДОПОМІЖНІ ФУНКЦІЇ ---
def show_pdf(file_path):
    try:
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Не вдалося відкрити PDF: {e}")

# --- CALLBACKS ---
def on_person_selected():
    selected_label = st.session_state.person_selector
    if selected_label and selected_label != "-- Оберіть --":
        options_map = st.session_state.get('options_map', {})
        new_id = options_map.get(selected_label)
        if new_id:
            st.session_state.selected_person_id = new_id

def on_center_view():
    st.session_state.view_root_id = st.session_state.selected_person_id

def start_linking_mode(mode, role=None):
    st.session_state.linking_mode = mode
    st.session_state.linking_role = role
    st.session_state.linking_source_id = st.session_state.selected_person_id
    st.rerun()

def cancel_linking_mode():
    st.session_state.linking_mode = None
    st.session_state.linking_role = None
    st.session_state.linking_source_id = None
    st.rerun()

# --- 2. ВІЗУАЛІЗАЦІЯ (SVG) ---
def render_graph(dm: DataManager, selected_pid: str):
    if not dm.graph.nodes():
        st.info("Дерево порожнє. Додайте людей через меню зліва.")
        return None

    global_root = "1"
    if not dm.graph.has_node(global_root):
        global_root = list(dm.graph.nodes())[0] if dm.graph.nodes() else None

    custom_root = st.session_state.get('view_root_id')
    layout_root = custom_root if (custom_root and dm.graph.has_node(custom_root)) else global_root

    layout_engine = LayoutEngine()
    focus_id = selected_pid if selected_pid else layout_root

    positions = layout_engine.calculate_layout(dm.graph, layout_root)

    if not positions:
        st.error("Не вдалося розрахувати макет дерева.")
        return None

    renderer = SVGRenderer(dm.graph, positions, focus_id)
    svg_content = renderer.generate_svg()

    is_linking = st.session_state.get('linking_mode') is not None
    if is_linking:
        svg_content = re.sub(r"id='([^']+)'", r"id='LINK_\1'", svg_content)
        click_key = "graph_linking_mode"
    else:
        click_key = "graph_view_mode"

    clicked_id_raw = click_detector(svg_content, key=click_key)

    if clicked_id_raw and is_linking and clicked_id_raw.startswith("LINK_"):
        return clicked_id_raw.replace("LINK_", "")

    return clicked_id_raw

# --- 3. UI КОМПОНЕНТИ ---
def render_sidebar(dm: DataManager, authenticator):
    user_name = st.session_state.get('name', 'Користувач')
    st.sidebar.title(f"👤 {user_name}")
    authenticator.logout('🚪 Вийти', 'sidebar')

    st.sidebar.markdown("---")
    edit_mode = st.sidebar.toggle("🛠️ Режим редагування", value=False, key="edit_mode_toggle")

    # КНОПКА БЕКАПУ
    if edit_mode:
        col_backup, col_last = st.sidebar.columns([1, 2])
        if col_backup.button("☁️"):
            # Примусове скидання кешу, якщо треба
            # st.cache_resource.clear()
            perform_backup(manual=True)

        last_time = st.session_state.get('last_backup_time')
        if last_time:
            time_str = last_time.strftime("%H:%M")
            col_last.caption(f"Останній: {time_str}")
        else:
            col_last.caption("Бекапів не було")

    with st.sidebar.expander("ℹ️ Легенда кольорів", expanded=False):
        st.markdown("""
        <div style="font-size: 12px;">
        <span style="color:#FFD700; font-size:16px;">■</span> <b>Жовтий</b>: Вибрана людина<br>
        <span style="color:#87CEEB; font-size:16px;">■</span> <b>Блакитний</b>: Предки<br>
        <span style="color:#98FB98; font-size:16px;">■</span> <b>Зелений</b>: Нащадки<br>
        <span style="color:#FFB6C1; font-size:16px;">■</span> <b>Рожевий</b>: Партнери<br>
        <span style="color:#DDA0DD; font-size:16px;">■</span> <b>Фіолетовий</b>: Брати/Сестри
        </div>
        """, unsafe_allow_html=True)

    st.sidebar.markdown("---")

    people = dm.get_all_people()
    if people:
        options_map = {f"{label} (ID: {pid})": pid for pid, label in people}
        st.session_state.options_map = options_map
        sorted_labels = sorted(options_map.keys())

        current_index = 0
        current_pid = st.session_state.get('selected_person_id')

        if current_pid:
            for idx, label in enumerate(sorted_labels):
                if options_map[label] == current_pid:
                    current_index = idx + 1
                    break

        st.sidebar.selectbox(
            "🔍 Знайти / Редагувати",
            ["-- Оберіть --"] + sorted_labels,
            index=current_index,
            key="person_selector",
            on_change=on_person_selected
        )

        st.sidebar.button("🎯 Центрувати дерево на вибраному", on_click=on_center_view)

    if edit_mode:
        st.sidebar.markdown("---")
        with st.sidebar.form("add_person_form"):
            st.write("➕ **Додати нову людину**")
            new_name = st.text_input("Введіть ПІБ")
            if st.form_submit_button("Додати"):
                if new_name:
                    new_id = dm.add_person(new_name)
                    st.session_state.selected_person_id = new_id
                    save_state(dm)

        if not people and st.sidebar.button("🛠 Тестові дані"):
            dm.create_test_data(); save_state(dm)

    # ЛОГИ АКТИВНОСТІ
    with st.sidebar.expander("📜 Історія змін", expanded=False):
        logs = dm.logger.get_recent_logs(10)
        if not logs:
            st.write("Історія порожня.")
        else:
            for timestamp, user, action, details in logs:
                st.markdown(f"**{action}** ({user})")
                st.caption(f"{details} | {timestamp}")
                st.markdown("---")

    return edit_mode

def render_main_area(dm: DataManager, is_editing: bool):
    selected_pid = st.session_state.get('selected_person_id')
    linking_mode = st.session_state.get('linking_mode')

    if linking_mode:
        role_text = st.session_state.get('linking_role', '')
        if role_text == 'father': role_str = "БАТЬКА"
        elif role_text == 'mother': role_str = "МАТІР"
        elif linking_mode == 'partner': role_str = "ПАРТНЕРА"
        elif linking_mode == 'child': role_str = "ДИТИНУ"
        else: role_str = "РОДИЧА"

        st.warning(f"🔗 **ОБЕРІТЬ {role_str} НА ГРАФІ НИЖЧЕ** (або натисніть 'Скасувати')")
        if st.button("❌ Скасувати"):
            cancel_linking_mode()

    st.subheader("📊 Генеалогічне Дерево")

    clicked_node_id = render_graph(dm, selected_pid)

    if clicked_node_id:
        if linking_mode:
            source = st.session_state.linking_source_id
            target = clicked_node_id

            if source == target:
                st.toast("❌ Не можна поєднати людину з собою!", icon="⚠️")
            else:
                try:
                    if linking_mode == 'parent':
                        role = st.session_state.linking_role
                        dm.add_parent(source, target, role)
                    elif linking_mode == 'partner':
                        dm.add_partner(source, target)
                    elif linking_mode == 'child':
                        dm.add_child(source, target)

                    st.success("Зв'язок створено!")
                    cancel_linking_mode()
                    save_state(dm)
                except Exception as e:
                    st.error(f"Помилка: {e}")

        elif clicked_node_id != selected_pid:
            st.session_state.selected_person_id = clicked_node_id
            st.rerun()

    st.markdown("---")

    if selected_pid and dm.graph.has_node(selected_pid):
        render_edit_panel(dm, selected_pid, is_editing)
    else:
        if not linking_mode:
            st.info("👈 Клікніть на людину в дереві або оберіть зі списку.")

def render_edit_panel(dm: DataManager, pid: str, is_editing: bool):
    data = dm.get_person_data(pid)

    root_id = st.session_state.get('view_root_id')
    if not root_id or not dm.graph.has_node(root_id):
        root_id = "1" if dm.graph.has_node("1") else pid

    rel_calc = RelationshipCalculator(dm.graph)
    _, rel_name = rel_calc.get_relationship_type(root_id, pid)
    root_name = dm.graph.nodes[root_id].get('label', 'Центр') if dm.graph.has_node(root_id) else "..."

    st.markdown(f"""
    <div style="padding: 15px; background-color: #262730; border-radius: 10px; border-left: 5px solid #FFD700; margin-bottom: 20px;">
        <h2 style="margin:0; padding:0;">✏️ {data.get('label')}</h2>
        <p style="margin:5px 0 0 0; color: #aaa;">
            Відносно <b>{root_name}</b>: <span style="color: #FFD700; font-weight: bold;">{rel_name}</span>
        </p>
    </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs(["📝 Інфо", "🔗 Зв'язки", "📎 Документи", "🗑️ Видалення"])

    # 1. ІНФО
    with tabs[0]:
        c1, c2 = st.columns(2)
        if is_editing:
            with c1:
                name = st.text_input("ПІБ", data.get('label', ''), key="edit_name")
                dob = st.text_input("Д.Н.", data.get('date_of_birth', ''), key="edit_dob")
            with c2:
                dod = st.text_input("Д.С.", data.get('date_of_death', ''), key="edit_dod")
            notes = st.text_area("Нотатки", data.get('notes', ''), key="edit_notes")
            if st.button("Зберегти зміни", type="primary"):
                dm.update_person(pid, name=name, birth_date=dob)
                dm.graph.nodes[pid]['date_of_death'] = dod
                dm.save_notes(pid, notes)
                save_state(dm)
        else:
            with c1:
                st.write(f"**ПІБ:** {data.get('label', '—')}")
                st.write(f"**Дата народження:** {data.get('date_of_birth', '—')}")
            with c2:
                st.write(f"**Дата смерті:** {data.get('date_of_death', '—')}")
            st.divider()
            st.write("**Нотатки:**")
            st.write(data.get('notes', '—'))

    # 2. ЗВ'ЯЗКИ
    with tabs[1]:
        all_p = dm.get_all_people()
        opts = {f"{l} ({i})": i for i, l in all_p if i != pid}

        parents = dm.get_parents(pid)
        partners = dm.get_partners(pid)
        children = dm.get_children(pid)

        st.write("#### 👨‍👩‍👧‍👦 Родина")
        if parents[0]: st.write(f"👴 **Батько:** {dm.graph.nodes[parents[0]]['label']}")
        if parents[1]: st.write(f"👵 **Мати:** {dm.graph.nodes[parents[1]]['label']}")
        if partners: st.write(f"❤️ **Партнери:** {', '.join([dm.graph.nodes[p]['label'] for p in partners])}")
        if children: st.write(f"👶 **Діти:** {', '.join([dm.graph.nodes[c]['label'] for c in children])}")

        if is_editing:
            st.divider()
            st.write("#### ➕ Змінити зв'язки")

            # --- БАТЬКИ ---
            st.markdown("##### Батьки")
            col1, col2 = st.columns([2, 1])
            with col1:
                p_sel = st.selectbox("Оберіть зі списку", ["--"]+list(opts.keys()), key="p_parent_sel")
                role_dict = {"Батько": "father", "Мати": "mother"}
                role_ua = st.radio("Роль", ["Батько", "Мати"], horizontal=True, key="p_role_sel")
                if st.button("Додати", key="btn_add_parent_list"):
                    if p_sel != "--":
                        dm.add_parent(pid, opts[p_sel], role_dict[role_ua])
                        save_state(dm)
            with col2:
                st.write("")
                st.write("")
                if st.button("🎯 Обрати на графі", key="btn_link_parent"):
                    start_linking_mode('parent', role_dict[role_ua])

            st.markdown("---")
            # --- ПАРТНЕРИ ---
            st.markdown("##### Партнери")
            col1, col2 = st.columns([2, 1])
            with col1:
                pt_sel = st.selectbox("Оберіть зі списку", ["--"]+list(opts.keys()), key="p_partner_sel")
                if st.button("Додати", key="btn_add_partner_list"):
                    if pt_sel != "--":
                        dm.add_partner(pid, opts[pt_sel])
                        save_state(dm)
            with col2:
                st.write("")
                if st.button("🎯 Обрати на графі", key="btn_link_partner"):
                    start_linking_mode('partner')

            st.markdown("---")
            # --- ДІТИ ---
            st.markdown("##### Діти")
            col1, col2 = st.columns([2, 1])
            with col1:
                ch_sel = st.selectbox("Оберіть зі списку", ["--"]+list(opts.keys()), key="p_child_sel")
                if st.button("Додати", key="btn_add_child_list"):
                    if ch_sel != "--":
                        dm.add_child(pid, opts[ch_sel])
                        save_state(dm)
            with col2:
                st.write("")
                if st.button("🎯 Обрати на графі", key="btn_link_child"):
                    start_linking_mode('child')

    # 3. ДОКУМЕНТИ
    with tabs[2]:
        st.write("📂 **Файли та зображення**")

        if is_editing:
            if 'uploader_key' not in st.session_state:
                st.session_state.uploader_key = 0

            up_tab1, up_tab2 = st.tabs(["📤 Завантажити файл", "📸 Зробити фото"])

            with up_tab1:
                uploaded_file = st.file_uploader(
                    "Виберіть документ",
                    key=f"file_upl_{st.session_state.uploader_key}"
                )
                if uploaded_file is not None:
                    if st.button("Завантажити", key="btn_upl_file"):
                        if dm.save_document_file(pid, uploaded_file):
                            st.session_state.uploader_key += 1
                            save_state(dm)
                            st.success("Файл збережено!")

            with up_tab2:
                camera_file = st.camera_input(
                    "Зробіть фото документа",
                    key=f"cam_upl_{st.session_state.uploader_key}"
                )
                if camera_file is not None:
                    import datetime
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    camera_file.name = f"scan_{ts}.jpg"

                    if st.button("Зберегти фото", key="btn_upl_cam"):
                        if dm.save_document_file(pid, camera_file):
                            st.session_state.uploader_key += 1
                            save_state(dm)
                            st.success("Фото збережено!")

            st.divider()

        docs = dm.get_person_documents(pid)
        if not docs:
            st.info("Немає документів.")
        else:
            for doc in docs:
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.write(f"📄 **{doc['filename']}**")
                    if doc['type'] == 'image':
                        # ВИПРАВЛЕНО: 'auto' замість 'stretch' для st.image
                        st.image(doc['path'], caption=doc['filename'], width=None)
                    elif doc['filename'].lower().endswith('.pdf'):
                        with st.expander("👁️ Переглянути PDF"):
                            show_pdf(doc['path'])
                with c2:
                    with open(doc['path'], "rb") as f:
                        st.download_button("⬇️ Скачати", f, file_name=doc['filename'], key=f"dl_{doc['filename']}")
                    if is_editing:
                        if st.button("🗑️ Видалити", key=f"del_{doc['filename']}"):
                            dm.delete_document_file(pid, doc['filename'])
                            save_state(dm)
                st.divider()

    # 4. ВИДАЛЕННЯ
    with tabs[3]:
        if is_editing:
            st.warning("Будьте обережні. Ця дія незворотна.")
            if st.button("🗑️ Видалити людину назавжди", type="secondary"):
                dm.delete_person(pid)
                st.session_state.selected_person_id = None
                if st.session_state.view_root_id == pid:
                    st.session_state.view_root_id = None
                save_state(dm)
        else:
            st.info("Видалення доступне тільки в режимі редагування.")

# --- 4. ГОЛОВНИЙ ЗАПУСК ---
def main():
    try:
        def safe_convert(obj):
            if isinstance(obj, list): return [safe_convert(x) for x in obj]
            if hasattr(obj, "items"): return {k: safe_convert(v) for k, v in obj.items()}
            return obj

        if 'credentials' not in st.session_state:
            st.session_state['credentials'] = safe_convert(st.secrets['credentials'])

        credentials = st.session_state['credentials']
        cookie_params = st.secrets['cookie']

    except Exception as e:
        st.error(f"❌ Помилка ініціалізації: {e}")
        st.stop()

    authenticator = stauth.Authenticate(
        credentials,
        cookie_params['name'],
        cookie_params['key'],
        cookie_params['expiry_days']
    )

    if check_session_timeout(authenticator): return

    try:
        authenticator.login(location='main')
    except Exception as e:
        st.error(f"Помилка входу: {e}")

    if st.session_state.get("authentication_status"):
        if 'selected_person_id' not in st.session_state:
            st.session_state.selected_person_id = None
        if 'view_root_id' not in st.session_state:
            st.session_state.view_root_id = None
        if 'linking_mode' not in st.session_state:
            st.session_state.linking_mode = None

        dm = get_data_manager()
        is_editing = render_sidebar(dm, authenticator)
        render_main_area(dm, is_editing)

    elif st.session_state.get("authentication_status") is False:
        st.error('❌ Невірний логін або пароль')
        brute_force_protection()

    elif st.session_state.get("authentication_status") is None:
        st.warning('🔐 Будь ласка, введіть логін та пароль')

if __name__ == "__main__":
    main()
```

**File: `run_tests.py`**
```python
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
```

**File: `tree_view.py`**
```python
from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsRectItem,
                               QGraphicsTextItem, QPushButton, QWidget, QVBoxLayout, QLabel)
from PySide6.QtGui import QColor, QBrush, QPen, QFont, QPainter, QPolygonF
from PySide6.QtCore import Qt, Signal, QPointF, QPoint
import networkx as nx
from collections import defaultdict

from layout_engine import LayoutEngine, NODE_WIDTH, NODE_HEIGHT, REL_PARTNER, REL_CHILD
from relationship_calculator import RelationshipCalculator
from info_bubble import BubbleContainer


class ClickableNode(QGraphicsRectItem):
    """Вузол, на який можна клікати."""

    def __init__(self, node_id: str, tree_view: 'TreeView', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.node_id = node_id
        self.tree_view = tree_view
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.tree_view.on_node_click(self.node_id)
            event.accept()
        elif event.button() == Qt.RightButton:
            screen_pos = event.screenPos()
            if hasattr(screen_pos, 'toPoint'):
                pos = screen_pos.toPoint()
            else:
                pos = QPoint(int(screen_pos.x()), int(screen_pos.y()))

            self.tree_view.show_bubbles(self.node_id, pos)
            event.accept()

    def hoverEnterEvent(self, event):
        self.tree_view.show_person_tooltip(self.node_id)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.tree_view.hide_person_tooltip()
        super().hoverLeaveEvent(event)


class LegendWidget(QWidget):
    """Віджет легенди кольорів."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 180);
                border: 2px solid rgba(255, 255, 255, 100);
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton {
                background-color: rgba(50, 50, 50, 200);
                color: white;
                border: 1px solid gray;
                border-radius: 3px;
                padding: 2px 5px;
            }
            QPushButton:hover {
                background-color: rgba(70, 70, 70, 200);
            }
        """)
        self.is_collapsed = False
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)

        self.toggle_btn = QPushButton("▼ Згорнути")
        self.toggle_btn.clicked.connect(self.toggle_collapse)
        layout.addWidget(self.toggle_btn)

        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(5)

        legend_data = [
            ("🟡 Фокусна людина", "#FFD700"),
            ("🔵 Батьки/Предки", "#87CEEB"),
            ("🟢 Діти/Нащадки", "#98FB98"),
            ("🌸 Партнери", "#FFB6C1"),
            ("🟣 Брати/Сестри", "#DDA0DD"),
            ("🟠 Дядьки/Племінники", "#FFD700"),
            ("⚪ Далекі родичі", "#E6E6FA"),
        ]

        for label, color in legend_data:
            qlabel = QLabel(label)
            qlabel.setStyleSheet(f"""
                background-color: {color};
                color: black;
                padding: 3px;
                border-radius: 3px;
                font-size: 10px;
            """)
            content_layout.addWidget(qlabel)

        instruction = QLabel("ℹ️ ПКМ на людині - бабли")
        instruction.setStyleSheet("""
            background-color: rgba(100, 100, 100, 200);
            color: white;
            padding: 3px;
            border-radius: 3px;
            font-size: 9px;
        """)
        content_layout.addWidget(instruction)

        layout.addWidget(self.content_widget)
        self.adjustSize()

    def toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed
        if self.is_collapsed:
            self.content_widget.hide()
            self.toggle_btn.setText("▶ Розгорнути")
        else:
            self.content_widget.show()
            self.toggle_btn.setText("▼ Згорнути")
        self.adjustSize()


class TooltipWidget(QWidget):
    """Спливаюча підказка."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 220);
                border: 2px solid rgba(255, 215, 0, 200);
                border-radius: 8px;
                padding: 10px;
                color: white;
            }
        """)
        self.setup_ui()
        self.hide()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        self.name_label = QLabel()
        self.name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFD700;")
        layout.addWidget(self.name_label)

        self.relationship_label = QLabel()
        self.relationship_label.setStyleSheet("font-size: 12px; color: #87CEEB;")
        layout.addWidget(self.relationship_label)

        self.dob_label = QLabel()
        self.dob_label.setStyleSheet("font-size: 11px; color: #98FB98;")
        layout.addWidget(self.dob_label)

        self.notes_label = QLabel()
        self.notes_label.setStyleSheet("font-size: 10px; color: #D3D3D3;")
        self.notes_label.setWordWrap(True)
        layout.addWidget(self.notes_label)

    def update_info(self, name: str, relationship: str, dob: str = "", dod: str = "", notes: str = ""):
        self.name_label.setText(name)
        self.relationship_label.setText(f"Зв'язок: {relationship}")

        dob_text = f"Дата народження: {dob}" if dob else ""
        dod_text = f"\n† {dod}" if dod else ""
        self.dob_label.setText(dob_text + dod_text)

        if notes:
            short_notes = notes[:100] + "..." if len(notes) > 100 else notes
            self.notes_label.setText(short_notes)
        else:
            self.notes_label.setText("")

        self.adjustSize()


class TreeView(QGraphicsView):
    """
    Основний віджет відображення дерева.
    """
    node_clicked = Signal(str)
    bubbles_updated = Signal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)

        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(QColor(30, 30, 40)))

        self.font = QFont("DejaVu Sans", 10)
        self.layout_engine = LayoutEngine()

        self.current_graph = None
        self.current_positions = None
        self.current_focus_id = None

        self.relationship_calc = None
        self.data_manager = None

        self.legend = LegendWidget(self)
        self.legend.move(10, 10)
        self.legend.show()

        self.tooltip = TooltipWidget(self)

        self.bubble_container = None
        self.current_bubble_person_id = None

    def set_data_manager(self, data_manager):
        self.data_manager = data_manager

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.legend.move(10, 10)

    def on_node_click(self, node_id: str):
        self.current_focus_id = node_id
        self.node_clicked.emit(node_id)
        self.refresh_colors_only()

    def update_view(self, graph: nx.DiGraph, focus_node_id: str = None):
        self.current_graph = graph
        self.current_focus_id = focus_node_id
        self.relationship_calc = RelationshipCalculator(graph)

        if not graph or graph.number_of_nodes() == 0:
            self.scene.clear()
            return

        self.current_positions = self.layout_engine.calculate_layout(graph, focus_node_id)

        if self.current_positions is None:
            self.scene.clear()
            error_text = self.scene.addText("Помилка компонування або порожнє дерево.")
            error_text.setDefaultTextColor(Qt.white)
            return

        self.redraw_scene()

        if focus_node_id and focus_node_id in self.current_positions:
            self._center_on_node(focus_node_id)

    def refresh_colors_only(self):
        if self.current_graph and self.current_positions:
            self.redraw_scene(keep_view=True)

    def redraw_scene(self, keep_view=False):
        center_point = None
        if keep_view:
            center_point = self.mapToScene(self.viewport().rect().center())

        self.scene.clear()

        if self.bubble_container:
            self.bubble_container.hide()
            self.bubble_container = None

        if not self.current_graph or not self.current_positions:
            return

        positions = self.current_positions
        graph = self.current_graph
        focus_id = self.current_focus_id

        # --- 1. МАЛЮЄМО ЗВ'ЯЗКИ ---
        child_to_parents = defaultdict(set)

        for child_id in graph.nodes():
            node_data = graph.nodes[child_id]
            father = node_data.get('father')
            mother = node_data.get('mother')
            if father: child_to_parents[child_id].add(father)
            if mother: child_to_parents[child_id].add(mother)

        for u, v, attrs in graph.edges(data=True):
            if attrs.get('type') == REL_CHILD:
                child_to_parents[v].add(u)

        family_children = defaultdict(list)
        for child_id, parents_set in child_to_parents.items():
            if child_id not in positions: continue
            parents_in_pos = [p for p in parents_set if p in positions]
            if parents_in_pos:
                parents_key = tuple(sorted(parents_in_pos))
                family_children[parents_key].append(child_id)

        for parents_key, children in family_children.items():
            if not children: continue
            parents = list(parents_key)
            if not parents: continue

            # ОТРИМУЄМО КОЛІР (вже як QColor через допоміжний метод)
            edge_color = self._get_edge_color_for_line(parents[0], children[0])
            pen = QPen(edge_color, 2)

            if len(parents) >= 2:
                p1_pos = positions[parents[0]]
                p2_pos = positions[parents[1]]
                parent_center_x = (p1_pos[0] + p2_pos[0]) / 2
                parent_bottom_y = max(p1_pos[1], p2_pos[1]) + NODE_HEIGHT / 2
            else:
                p_pos = positions[parents[0]]
                parent_center_x = p_pos[0]
                parent_bottom_y = p_pos[1] + NODE_HEIGHT / 2

            children_top_y = min(positions[c][1] for c in children) - NODE_HEIGHT / 2
            branch_y = parent_bottom_y + (children_top_y - parent_bottom_y) * 0.4

            self.scene.addLine(parent_center_x, parent_bottom_y,
                               parent_center_x, branch_y, pen)

            children_x = [positions[c][0] for c in children]
            min_child_x = min(children_x)
            max_child_x = max(children_x)

            if len(children) > 1 or abs(parent_center_x - children_x[0]) > 1:
                line_start_x = min(min_child_x, parent_center_x)
                line_end_x = max(max_child_x, parent_center_x)
                self.scene.addLine(line_start_x, branch_y, line_end_x, branch_y, pen)

            for child_id in children:
                child_x = positions[child_id][0]
                child_top_y = positions[child_id][1] - NODE_HEIGHT / 2
                self.scene.addLine(child_x, branch_y, child_x, child_top_y, pen)

        # --- 2. МАЛЮЄМО ВУЗЛИ ---
        for node_id, attrs in graph.nodes(data=True):
            if node_id in positions:
                x, y = positions[node_id]

                # ОТРИМУЄМО HEX ТА КОНВЕРТУЄМО В QColor
                fill_hex, border_hex, width = self.relationship_calc.get_node_color(focus_id, node_id)

                fill_color = QColor(fill_hex)
                border_color = QColor(border_hex)

                rect = ClickableNode(node_id, self, x - NODE_WIDTH / 2, y - NODE_HEIGHT / 2,
                                     NODE_WIDTH, NODE_HEIGHT)
                rect.setBrush(QBrush(fill_color))
                rect.setPen(QPen(border_color, width))
                self.scene.addItem(rect)

                label_text = attrs.get('label', '')
                if len(label_text) > 18:
                    label_text = label_text[:16] + "..."

                text = QGraphicsTextItem(label_text)
                text.setDefaultTextColor(QColor(0, 0, 0))
                text.setFont(self.font)

                brect = text.boundingRect()
                text.setPos(x - brect.width() / 2, y - brect.height() / 2)
                self.scene.addItem(text)

                rect.setZValue(10)
                text.setZValue(11)

        if keep_view and center_point:
            self.centerOn(center_point)

    def _center_on_node(self, node_id):
        if self.current_positions and node_id in self.current_positions:
            x, y = self.current_positions[node_id]
            self.centerOn(x, y)

    def _get_edge_color_for_line(self, parent_id, child_id):
        """Отримує HEX колір і повертає QColor."""
        if not self.relationship_calc or not self.current_focus_id:
            return QColor(100, 100, 100)

        if not parent_id:
            return QColor(100, 100, 100)

        hex_color = self.relationship_calc.get_edge_color(self.current_focus_id, parent_id, child_id)
        return QColor(hex_color)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def show_bubbles(self, person_id: str, screen_position: QPoint):
        if self.bubble_container:
            self.bubble_container.hide()
            self.bubble_container.deleteLater()
            self.bubble_container = None

        self.bubble_container = BubbleContainer(person_id, self)
        self.current_bubble_person_id = person_id

        if self.relationship_calc and self.current_focus_id:
            _, relationship_name = self.relationship_calc.get_relationship_type(
                self.current_focus_id, person_id
            )
            self.bubble_container.set_relationship_text(relationship_name)

        if self.data_manager and self.data_manager.graph.has_node(person_id):
            person_data = self.data_manager.graph.nodes[person_id]
            bubbles_data = person_data.get('bubbles', [])

            for i, bubble_data in enumerate(bubbles_data):
                if i < 5:
                    self.bubble_container.set_bubble_data(i + 1, bubble_data)

        self.bubble_container.bubble_edited.connect(self.on_bubble_edited)
        self.bubble_container.close_requested.connect(self.hide_bubbles)

        local_pos = self.mapFromGlobal(screen_position)
        x = local_pos.x() + 20
        y = local_pos.y() - 50

        if x + self.bubble_container.width() > self.width():
            x = local_pos.x() - self.bubble_container.width() - 20
        if y < 0:
            y = 10
        elif y + self.bubble_container.height() > self.height():
            y = self.height() - self.bubble_container.height() - 10

        self.bubble_container.move(x, y)
        self.bubble_container.show()
        self.bubble_container.raise_()

    def hide_bubbles(self):
        if self.bubble_container:
            self.bubble_container.hide()
            self.bubble_container.deleteLater()
            self.bubble_container = None

    def on_bubble_edited(self, person_id: str, bubble_id: int, data: dict):
        if not self.data_manager or not self.data_manager.graph.has_node(person_id):
            return

        person_data = self.data_manager.graph.nodes[person_id]
        if 'bubbles' not in person_data:
            person_data['bubbles'] = [{} for _ in range(5)]

        person_data['bubbles'][bubble_id - 1] = data
        self.data_manager.save_project()
        self.bubbles_updated.emit(person_id, person_data['bubbles'])

    def show_person_tooltip(self, person_id: str):
        if not self.relationship_calc or not self.current_focus_id:
            return

        person_data = self.relationship_calc.graph.nodes.get(person_id, {})
        _, relationship_name = self.relationship_calc.get_relationship_type(
            self.current_focus_id, person_id
        )

        name = person_data.get('label', 'Невідомо')
        dob = person_data.get('date_of_birth', '')
        dod = person_data.get('date_of_death', '')

        notes = ""
        if self.data_manager:
            full_notes = self.data_manager.load_notes(person_id)
            notes = full_notes[:150] if full_notes else ""

        self.tooltip.update_info(name, relationship_name, dob, dod, notes)

        cursor_pos = self.mapFromGlobal(self.cursor().pos())
        self.tooltip.move(cursor_pos.x() + 20, cursor_pos.y() + 20)
        self.tooltip.show()

    def hide_person_tooltip(self):
        self.tooltip.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.bubble_container and self.bubble_container.isVisible():
                if not self.bubble_container.geometry().contains(event.pos()):
                    self.hide_bubbles()
        super().mousePressEvent(event)
```

**File: `data_manager.py`**
```python
"""
Data Manager for Family Tree - Web Version.
Handles JSON loading/saving + Logging.
"""

import json
import os
import networkx as nx
import shutil
from utils.logger_service import LoggerService  # <--- ІМПОРТ

# Relationship type constants
REL_PARTNER = 'partner'
REL_CHILD = 'child'

class DataManager:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.project_file_path = ""
        self.project_directory = ""
        self.next_person_id = 1
        self.logger = LoggerService()  # <--- ІНІЦІАЛІЗАЦІЯ

    def load_project(self, filepath: str) -> bool:
        self.project_file_path = os.path.abspath(filepath)
        self.project_directory = os.path.dirname(self.project_file_path)

        if not os.path.exists(self.project_directory):
            os.makedirs(self.project_directory, exist_ok=True)

        if os.path.exists(self.project_file_path):
            try:
                with open(self.project_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.graph = nx.node_link_graph(data, edges="links")

                node_ids = [int(node_id) for node_id in self.graph.nodes() if node_id.isdigit()]
                self.next_person_id = max(node_ids) + 1 if node_ids else 1
                return True
            except Exception as e:
                print(f"Error loading project: {e}")
                return False
        else:
            return True

    def save_project(self) -> bool:
        try:
            data = nx.node_link_data(self.graph, edges="links")
            with open(self.project_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving project: {e}")
            return False

    def add_person(self, name: str) -> str:
        person_id = str(self.next_person_id)
        self.next_person_id += 1

        self.graph.add_node(person_id, label=name, documents=[], birth_date="", notes="")

        person_dir = os.path.join(self.project_directory, f"{person_id}_{name}")
        os.makedirs(person_dir, exist_ok=True)

        self.logger.log("ADD_PERSON", f"Created {name} (ID: {person_id})") # <--- LOG
        return person_id

    def update_person(self, person_id: str, name: str = None, birth_date: str = None) -> bool:
        if not self.graph.has_node(person_id): return False

        changes = []
        if name is not None:
            old_name = self.graph.nodes[person_id].get('label', 'Unknown')
            if old_name != name:
                old_dir = os.path.join(self.project_directory, f"{person_id}_{old_name}")
                new_dir = os.path.join(self.project_directory, f"{person_id}_{name}")
                if os.path.exists(old_dir):
                    try:
                        os.rename(old_dir, new_dir)
                    except OSError: pass
                changes.append(f"Name: {old_name} -> {name}")
            self.graph.nodes[person_id]['label'] = name

        if birth_date is not None:
            self.graph.nodes[person_id]['birth_date'] = birth_date
            changes.append(f"DOB updated")

        if changes:
            self.logger.log("UPDATE_PERSON", f"ID {person_id}: {', '.join(changes)}") # <--- LOG
        return True

    def delete_person(self, person_id: str) -> bool:
        if not self.graph.has_node(person_id): return False

        name = self.graph.nodes[person_id].get('label', '?')
        person_label = self.graph.nodes[person_id].get('label', 'Unknown')
        person_dir = os.path.join(self.project_directory, f"{person_id}_{person_label}")
        if os.path.exists(person_dir): shutil.rmtree(person_dir)

        # Clean relations
        for node_id, node_data in list(self.graph.nodes(data=True)):
            if node_data.get('father') == person_id: self.graph.nodes[node_id]['father'] = None
            if node_data.get('mother') == person_id: self.graph.nodes[node_id]['mother'] = None

        self.graph.remove_node(person_id)
        self.logger.log("DELETE_PERSON", f"Deleted {name} (ID: {person_id})") # <--- LOG
        return True

    def save_notes(self, person_id: str, notes_content: str):
        if not self.graph.has_node(person_id): return
        self.graph.nodes[person_id]['notes'] = notes_content

        person_label = self.graph.nodes[person_id].get('label', 'Unknown')
        person_dir = os.path.join(self.project_directory, f"{person_id}_{person_label}")
        os.makedirs(person_dir, exist_ok=True)

        try:
            with open(os.path.join(person_dir, "notes.txt"), 'w', encoding='utf-8') as f:
                f.write(notes_content)
            self.logger.log("UPDATE_NOTES", f"Updated notes for ID {person_id}") # <--- LOG
        except: pass
        self.save_project()

    def load_notes(self, person_id: str) -> str:
        if not self.graph.has_node(person_id): return ""
        person_label = self.graph.nodes[person_id].get('label', 'Unknown')
        notes_file = os.path.join(self.project_directory, f"{person_id}_{person_label}", "notes.txt")
        if os.path.exists(notes_file):
            try:
                with open(notes_file, 'r', encoding='utf-8') as f: return f.read()
            except: pass
        return self.graph.nodes[person_id].get('notes', '')

    def save_document_file(self, person_id: str, uploaded_file) -> bool:
        if not self.graph.has_node(person_id): return False
        person_label = self.graph.nodes[person_id].get('label', 'Unknown')
        person_dir = os.path.join(self.project_directory, f"{person_id}_{person_label}")
        os.makedirs(person_dir, exist_ok=True)

        try:
            with open(os.path.join(person_dir, uploaded_file.name), "wb") as f:
                f.write(uploaded_file.getbuffer())

            if 'documents' not in self.graph.nodes[person_id]:
                self.graph.nodes[person_id]['documents'] = []

            exists = any(d['filename'] == uploaded_file.name for d in self.graph.nodes[person_id]['documents'])
            if not exists:
                self.graph.nodes[person_id]['documents'].append({
                    'filename': uploaded_file.name,
                    'display_name': uploaded_file.name
                })

            self.logger.log("ADD_DOC", f"Added {uploaded_file.name} to ID {person_id}") # <--- LOG
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False

    def delete_document_file(self, person_id: str, filename: str) -> bool:
        if not self.graph.has_node(person_id): return False
        person_label = self.graph.nodes[person_id].get('label', 'Unknown')
        file_path = os.path.join(self.project_directory, f"{person_id}_{person_label}", filename)

        if os.path.exists(file_path): os.remove(file_path)

        docs = self.graph.nodes[person_id].get('documents', [])
        self.graph.nodes[person_id]['documents'] = [d for d in docs if d['filename'] != filename]

        self.logger.log("DEL_DOC", f"Removed {filename} from ID {person_id}") # <--- LOG
        return True

    def get_person_documents(self, person_id: str) -> list:
        if not self.graph.has_node(person_id): return []
        person_label = self.graph.nodes[person_id].get('label', 'Unknown')
        person_dir = os.path.join(self.project_directory, f"{person_id}_{person_label}")
        docs = []
        if 'documents' in self.graph.nodes[person_id]:
            for doc in self.graph.nodes[person_id]['documents']:
                full_path = os.path.join(person_dir, doc['filename'])
                if os.path.exists(full_path):
                    docs.append({
                        'filename': doc['filename'],
                        'path': full_path,
                        'type': 'image' if doc['filename'].lower().endswith(('.png', '.jpg', '.jpeg')) else 'file'
                    })
        return docs

    def get_person_data(self, person_id: str) -> dict:
        if not self.graph.has_node(person_id): return {}
        data = dict(self.graph.nodes[person_id])
        data['id'] = person_id
        data['notes'] = self.load_notes(person_id)
        return data

    def get_all_people(self) -> list:
        return [(node_id, data.get('label', 'Unknown')) for node_id, data in self.graph.nodes(data=True)]

    def add_parent(self, child_id: str, parent_id: str, parent_type: str) -> bool:
        if not self.graph.has_node(child_id) or not self.graph.has_node(parent_id): return False
        self.graph.nodes[child_id][parent_type] = parent_id
        self.graph.add_edge(parent_id, child_id, type=REL_CHILD)

        c_name = self.graph.nodes[child_id]['label']
        p_name = self.graph.nodes[parent_id]['label']
        self.logger.log("LINK", f"{p_name} is {parent_type} of {c_name}") # <--- LOG
        return True

    def add_partner(self, person1_id: str, person2_id: str) -> bool:
        if not self.graph.has_node(person1_id) or not self.graph.has_node(person2_id): return False
        self.graph.add_edge(person1_id, person2_id, type=REL_PARTNER)
        self.graph.add_edge(person2_id, person1_id, type=REL_PARTNER)

        n1 = self.graph.nodes[person1_id]['label']
        n2 = self.graph.nodes[person2_id]['label']
        self.logger.log("LINK", f"{n1} partnered with {n2}") # <--- LOG
        return True

    def add_child(self, parent_id: str, child_id: str) -> bool:
        if not self.graph.has_node(parent_id) or not self.graph.has_node(child_id): return False
        child_data = self.graph.nodes[child_id]
        if not child_data.get('father'): child_data['father'] = parent_id
        elif not child_data.get('mother'): child_data['mother'] = parent_id
        self.graph.add_edge(parent_id, child_id, type=REL_CHILD)

        p_name = self.graph.nodes[parent_id]['label']
        c_name = self.graph.nodes[child_id]['label']
        self.logger.log("LINK", f"{c_name} added as child of {p_name}") # <--- LOG
        return True

    def get_parents(self, person_id: str) -> tuple:
        if not self.graph.has_node(person_id): return (None, None)
        data = self.graph.nodes[person_id]
        return (data.get('father'), data.get('mother'))

    def get_partners(self, person_id: str) -> list:
        partners = set()
        for u, v, attrs in self.graph.edges(person_id, data=True):
            if attrs.get('type') == REL_PARTNER: partners.add(v)
        for node_id, node_data in self.graph.nodes(data=True):
            if node_data.get('father') == person_id and node_data.get('mother'): partners.add(node_data['mother'])
            elif node_data.get('mother') == person_id and node_data.get('father'): partners.add(node_data['father'])
        return list(partners)

    def get_children(self, person_id: str) -> list:
        children = []
        for node_id, node_data in self.graph.nodes(data=True):
            if node_data.get('father') == person_id or node_data.get('mother') == person_id:
                children.append(node_id)
        return children

    def create_test_data(self):
        adam = self.add_person("Adam")
        eve = self.add_person("Eve")
        cain = self.add_person("Cain")
        abel = self.add_person("Abel")
        seth = self.add_person("Seth")
        enosh = self.add_person("Enosh")
        self.graph.add_edge(adam, eve, type=REL_PARTNER)
        self.graph.add_edge(eve, adam, type=REL_PARTNER)
        self.graph.nodes[cain]['father'] = adam
        self.graph.nodes[cain]['mother'] = eve
        self.graph.nodes[abel]['father'] = adam
        self.graph.nodes[abel]['mother'] = eve
        self.graph.nodes[seth]['father'] = adam
        self.graph.nodes[seth]['mother'] = eve
        self.graph.add_edge(adam, cain, type=REL_CHILD)
        self.graph.add_edge(eve, cain, type=REL_CHILD)
        self.graph.add_edge(adam, abel, type=REL_CHILD)
        self.graph.add_edge(eve, abel, type=REL_CHILD)
        self.graph.add_edge(adam, seth, type=REL_CHILD)
        self.graph.add_edge(eve, seth, type=REL_CHILD)
        self.graph.nodes[enosh]['father'] = seth
        self.graph.add_edge(seth, enosh, type=REL_CHILD)
        self.save_project()
```

**File: `relationship_calculator.py`**
```python
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
```

**File: `utils/auth_drive.py`**
```python
"""
Запустіть цей скрипт локально, щоб авторизуватися в Google Drive.
Він створить файл 'token.json', який потім використовуватиме програма.
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Ті самі права доступу
SCOPES = ['https://www.googleapis.com/auth/drive']


def authenticate():
    creds = None
    # Файл token.json зберігає токени доступу користувача.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # Якщо токени недійсні або відсутні - запускаємо вхід через браузер
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secret.json'):
                print("❌ Помилка: Файл 'client_secret.json' не знайдено.")
                print("1. Зайдіть в Google Cloud Console -> Credentials.")
                print("2. Створіть 'OAuth client ID' (Desktop app).")
                print("3. Скачайте JSON і перейменуйте в 'client_secret.json'.")
                return

            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Зберігаємо токен для наступних запусків
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print("✅ Авторизація успішна! Файл 'token.json' створено.")


if __name__ == '__main__':
    authenticate()
```

**File: `utils/hasher.py`**
```python
# utils/hasher.py
import bcrypt

# Список паролів, які ти хочеш використовувати
passwords_to_hash = ['admin123', 'f87A]35EDo32']

print("--- ЗБЕРЕЖИ ЦІ ХЕШІ У .streamlit/secrets.toml ---")

for password in passwords_to_hash:
    # Генеруємо сіль і хеш
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    # Декодуємо в стрічку для запису в TOML
    hashed_str = hashed.decode('utf-8')
    print(f'Password: "{password}" -> Hash: "{hashed_str}"')
```

**File: `utils/logger_service.py`**
```python
import csv
import os
from datetime import datetime

LOG_FILE = os.path.join("family_tree_data", "activity_log.csv")


class LoggerService:
    def __init__(self):
        if not os.path.exists(LOG_FILE):
            os.makedirs("family_tree_data", exist_ok=True)
            with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "User", "Action", "Details"])

    def log(self, action: str, details: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # --- УНІВЕРСАЛЬНЕ ВИЗНАЧЕННЯ КОРИСТУВАЧА ---
        user = "Desktop Admin"  # За замовчуванням
        try:
            import streamlit as st
            # Перевіряємо, чи ми в контексті Streamlit
            if hasattr(st, 'session_state') and 'name' in st.session_state:
                user = st.session_state['name']
        except ImportError:
            pass  # Якщо streamlit не встановлено або не запущено
        except Exception:
            pass  # Інші помилки контексту
        # -------------------------------------------

        try:
            with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, user, action, details])
        except Exception as e:
            print(f"Logging error: {e}")

    def get_recent_logs(self, limit=20):
        if not os.path.exists(LOG_FILE): return []
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                reader = list(csv.reader(f))
                if len(reader) < 2: return []
                data = reader[1:]
                return data[-limit:][::-1]
        except:
            return []
```

**File: `utils/security_utils.py`**
```python
# utils/security_utils.py
import time
import streamlit as st
from streamlit_authenticator import Authenticate

SESSION_TIMEOUT_MINUTES = 30


def check_session_timeout(authenticator: Authenticate):
    """
    Перевіряє час останньої активності. Якщо пройшло більше 30 хв — робить логаут.
    """
    if st.session_state.get("authentication_status"):
        last_activity = st.session_state.get('last_activity_time', time.time())
        current_time = time.time()

        # Перевірка тайм-ауту
        if (current_time - last_activity) > (SESSION_TIMEOUT_MINUTES * 60):
            authenticator.logout('main')
            st.warning("⏳ Сесія завершена через неактивність. Будь ласка, увійдіть знову.")
            st.session_state['last_activity_time'] = current_time  # скидання
            return True

        # Оновлення часу активності
        st.session_state['last_activity_time'] = current_time
    return False


def brute_force_protection():
    """
    Додає штучну затримку, якщо статус авторизації False (помилка входу).
    """
    if st.session_state.get("authentication_status") is False:
        time.sleep(2)  # Затримка 2 секунди при неправильному паролі
```

**File: `utils/persistence_service.py`**
```python
import os
import shutil
import streamlit as st
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# Константи
SCOPES = ['https://www.googleapis.com/auth/drive']
TOKEN_FILE = 'token.json'
LOCAL_DATA_DIR = 'family_tree_data'
ROOT_FOLDER_NAME = 'FamilyTreeBackup'


class PersistenceService:
    def __init__(self):
        self.creds = None
        self.service = None
        self.is_enabled = False
        self.root_folder_id = None
        self.status = "Initializing..."
        self._authenticate()

    def _authenticate(self):
        try:
            # Спроба отримати ID папки з секретів (якщо є)
            if 'backup_folder_id' in st.secrets:
                self.root_folder_id = st.secrets['backup_folder_id']

            # --- НОВА ЛОГІКА АВТОРИЗАЦІЇ (OAuth2) ---
            if os.path.exists(TOKEN_FILE):
                self.creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

            # Якщо токени протухли, спробуємо оновити (якщо це можливо без браузера)
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"Token refresh failed: {e}")
                    self.creds = None

            if self.creds and self.creds.valid:
                self.service = build('drive', 'v3', credentials=self.creds)
                self.is_enabled = True
                self.status = "Connected via User Token"
            else:
                self.status = "Token invalid or missing. Run utils/auth_drive.py"
                print(self.status)
                self.is_enabled = False

        except Exception as e:
            self.status = f"Auth Error: {e}"
            print(self.status)
            self.is_enabled = False

    def _get_or_create_folder(self, folder_name, parent_id=None):
        """Знаходить або створює папку на Drive."""
        if not self.service: return None

        q = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            q += f" and '{parent_id}' in parents"

        results = self.service.files().list(q=q, fields="files(id)").execute()
        items = results.get('files', [])

        if items:
            return items[0]['id']
        else:
            metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                metadata['parents'] = [parent_id]

            folder = self.service.files().create(body=metadata, fields='id').execute()
            return folder.get('id')

    def _upload_recursive(self, local_path, parent_drive_id):
        """Рекурсивно завантажує структуру папок."""
        if not os.path.exists(local_path): return

        for item in os.listdir(local_path):
            item_path = os.path.join(local_path, item)

            if os.path.isfile(item_path):
                # Завантаження файлу
                print(f"Uploading file: {item}")
                media = MediaFileUpload(item_path, resumable=True)
                metadata = {'name': item, 'parents': [parent_drive_id]}
                self.service.files().create(
                    body=metadata, media_body=media, fields='id'
                ).execute()

            elif os.path.isdir(item_path):
                # Створення папки
                print(f"Creating folder: {item}")
                new_folder_id = self._get_or_create_folder(item, parent_drive_id)
                self._upload_recursive(item_path, new_folder_id)

    def upload_backup(self):
        """Створює нову папку з датою і заливає туди всі дані."""
        if not self.is_enabled or not self.service:
            st.error(f"Хмара не підключена: {self.status}")
            return False

        try:
            # 1. Отримуємо/Створюємо кореневу папку 'FamilyTreeBackup'
            # (Тепер ми можемо її створити самі, бо ми діємо від імені користувача)
            if self.root_folder_id:
                root_id = self.root_folder_id  # Використовуємо ID з конфігу якщо є
            else:
                root_id = self._get_or_create_folder(ROOT_FOLDER_NAME)

            # 2. Створюємо папку конкретного бекапу з датою
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_folder_name = f"Backup_{timestamp}"

            print(f"Creating backup folder: {backup_folder_name}")
            backup_id = self._get_or_create_folder(backup_folder_name, root_id)

            # 3. Рекурсивно заливаємо вміст
            self._upload_recursive(LOCAL_DATA_DIR, backup_id)
            print(f"Backup complete: {backup_folder_name}")
            return True
        except Exception as e:
            st.error(f"Upload failed: {str(e)}")
            return False

    def _download_recursive(self, drive_folder_id, local_path):
        """Рекурсивно скачує вміст папки."""
        if not os.path.exists(local_path):
            os.makedirs(local_path, exist_ok=True)

        q = f"'{drive_folder_id}' in parents and trashed = false"
        results = self.service.files().list(q=q, fields="files(id, name, mimeType)").execute()
        items = results.get('files', [])

        for item in items:
            item_id = item['id']
            item_name = item['name']
            item_type = item['mimeType']
            local_item_path = os.path.join(local_path, item_name)

            if item_type == 'application/vnd.google-apps.folder':
                self._download_recursive(item_id, local_item_path)
            else:
                print(f"Downloading file: {item_name}")
                request = self.service.files().get_media(fileId=item_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()

                with open(local_item_path, 'wb') as f:
                    f.write(fh.getbuffer())

    def download_latest_backup(self):
        """Знаходить останній бекап."""
        if not self.is_enabled or not self.service: return False

        try:
            # Знаходимо корінь
            if self.root_folder_id:
                root_id = self.root_folder_id
            else:
                # Шукаємо за ім'ям, якщо ID не задано
                q = f"name = '{ROOT_FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
                res = self.service.files().list(q=q).execute()
                if not res.get('files'): return False
                root_id = res.get('files')[0]['id']

            # Шукаємо папки бекапів
            q = f"'{root_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            results = self.service.files().list(
                q=q, orderBy="createdTime desc", pageSize=1, fields="files(id, name)"
            ).execute()

            items = results.get('files', [])
            if not items:
                print("No backups found.")
                return False

            latest_backup = items[0]
            print(f"Downloading latest backup: {latest_backup['name']}")

            if os.path.exists(LOCAL_DATA_DIR):
                shutil.rmtree(LOCAL_DATA_DIR)

            self._download_recursive(latest_backup['id'], LOCAL_DATA_DIR)
            return True

        except Exception as e:
            print(f"Download failed: {e}")
            return False
```
