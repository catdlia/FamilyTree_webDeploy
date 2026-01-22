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