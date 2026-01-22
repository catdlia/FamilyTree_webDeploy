"""
Data Manager for Family Tree - Web Version.
Handles JSON loading/saving + Logging.
Supports Multi-Tenancy (User Isolation).
"""

import json
import os
import networkx as nx
import shutil
from utils.logger_service import LoggerService

# Relationship type constants
REL_PARTNER = 'partner'
REL_CHILD = 'child'

class DataManager:
    def __init__(self, username: str):
        self.username = username
        self.graph = nx.DiGraph()
        self.next_person_id = 1
        self.logger = LoggerService()

        # Головна папка даних
        self.root_data_dir = "family_tree_data"
        # Папка конкретного користувача
        self.project_directory = os.path.join(self.root_data_dir, self.username)
        # Файл дерева користувача
        self.project_file_path = os.path.join(self.project_directory, "family.tree")

        # Створюємо папку користувача, якщо її немає
        if not os.path.exists(self.project_directory):
            os.makedirs(self.project_directory, exist_ok=True)

    def load_project(self) -> bool:
        """Loads a project from user's folder."""
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

        # Створюємо папку для людини всередині папки користувача
        person_dir = os.path.join(self.project_directory, f"{person_id}_{name}")
        os.makedirs(person_dir, exist_ok=True)

        self.logger.log("ADD_PERSON", f"User {self.username} created {name} (ID: {person_id})")
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
            self.logger.log("UPDATE_PERSON", f"ID {person_id}: {', '.join(changes)}")
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
        self.logger.log("DELETE_PERSON", f"Deleted {name} (ID: {person_id})")
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

            self.logger.log("ADD_DOC", f"Added {uploaded_file.name} to ID {person_id}")
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

        self.logger.log("DEL_DOC", f"Removed {filename} from ID {person_id}")
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
        return True

    def add_partner(self, person1_id: str, person2_id: str) -> bool:
        if not self.graph.has_node(person1_id) or not self.graph.has_node(person2_id): return False
        self.graph.add_edge(person1_id, person2_id, type=REL_PARTNER)
        self.graph.add_edge(person2_id, person1_id, type=REL_PARTNER)
        return True

    def add_child(self, parent_id: str, child_id: str) -> bool:
        if not self.graph.has_node(parent_id) or not self.graph.has_node(child_id): return False
        child_data = self.graph.nodes[child_id]
        if not child_data.get('father'): child_data['father'] = parent_id
        elif not child_data.get('mother'): child_data['mother'] = parent_id
        self.graph.add_edge(parent_id, child_id, type=REL_CHILD)
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