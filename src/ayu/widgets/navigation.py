from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ayu.app import AyuApp
from textual import work
from textual.binding import Binding
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from ayu.utils import EventType
from ayu.constants import OUTCOME_SYMBOLS


class TestTree(Tree):
    app: "AyuApp"
    BINDINGS = [Binding("r", "refresh_tree", "Refresh")]
    show_root = False
    auto_expand = True
    guide_depth = 2

    def on_mount(self):
        self.app.dispatcher.register_handler(
            event_type=EventType.COLLECTION,
            handler=lambda data: self.build_tree(data),
        )
        self.app.dispatcher.register_handler(
            event_type=EventType.SCHEDULED,
            handler=lambda data: self.mark_tests_as_running(data),
        )
        self.app.dispatcher.register_handler(
            event_type=EventType.OUTCOME,
            handler=lambda data: self.update_test_outcome(data),
        )
        self.action_refresh_tree()

        return super().on_mount()

    @work(thread=True)
    def action_refresh_tree(self):
        import subprocess

        subprocess.run(
            # ["pytest", "--co"],
            ["uv", "run", "--with", "../ayu", "pytest", "--co"],
            capture_output=True,
        )

    def build_tree(self, collection_data: dict[Any, Any]):
        if collection_data:
            self.clear()
            self.update_tree(tree_data=collection_data["tree"])

    def update_tree(self, *, tree_data: dict[Any, Any]):
        parent = self.root

        def add_children(child_list: list[dict[Any, Any]], parent_node: TreeNode):
            for child in child_list:
                if child["children"]:
                    new_node = parent_node.add(
                        label=child["name"], data=child, expand=True
                    )
                    add_children(child_list=child["children"], parent_node=new_node)
                else:
                    parent_node.add_leaf(label=child["name"], data=child)

        for key, value in tree_data.items():
            if isinstance(value, dict) and "children" in value and value["children"]:
                node: TreeNode = parent.add(key, expand=True, data=value)
                add_children(value["children"], node)
            else:
                parent.add_leaf(key, data=key)

        # self.notify(f'{self._tree_nodes}', timeout=10)

    def update_test_outcome(self, test_result: dict):
        for node in self._tree_nodes.values():
            if node.data and (node.data.get("nodeid") == test_result.get("nodeid")):
                outcome = test_result["outcome"]
                node.label = f"{node.data['name']} {OUTCOME_SYMBOLS[outcome]}"

    def mark_tests_as_running(self, nodeids: list[str]) -> None:
        for node in self._tree_nodes.values():
            if (
                node.data
                # and isinstance(node.data, dict)
                and (node.data.get("nodeid") in nodeids)
            ):
                node.label = f"{node.data['name']} {OUTCOME_SYMBOLS['queued']}"
