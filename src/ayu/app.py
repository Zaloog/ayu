import os
from pathlib import Path
from textual import work, on
from textual.app import App
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.events import Key
from textual.widgets import Log, Header, Footer, Collapsible, Tree, Button
from textual.containers import Horizontal, Vertical
from textual_tags import Tag
from watchfiles import awatch, PythonFilter

from ayu.event_dispatcher import EventDispatcher
from ayu.constants import WEB_SOCKET_HOST, WEB_SOCKET_PORT
from ayu.utils import (
    EventType,
    NodeType,
    run_all_tests,
    remove_ansi_escapes,
    run_plugin_collection,
    run_test_collection,
)
from ayu.widgets.navigation import TestTree
from ayu.widgets.detail_viewer import DetailView, TestResultDetails
from ayu.widgets.filter import TreeFilter, MarkersFilter
from ayu.widgets.helper_widgets import ToggleRule, ButtonPanel
from ayu.widgets.modals.search import ModalSearch
from ayu.widgets.modals.plugin_manager import ModalPlugin
from ayu.widgets.coverage_explorer import CoverageExplorer
from ayu.widgets.log import OutputLog, LogViewer
from ayu.command_builder import build_command


class AyuApp(App):
    CSS_PATH = Path("assets/ayu.tcss")
    TOOLTIP_DELAY = 0.5

    BINDINGS = [
        Binding("ctrl+l", "run_tests", "Run Tests", show=True, priority=True),
        Binding("ctrl+l", "run_marked_tests", "Run ⭐ Tests", show=True, priority=True),
        Binding("s", "show_details", "Details", show=True),
        Binding("c", "clear_test_results", "Clear Results", show=True, priority=True),
        Binding("ctrl+r", "refresh", "Refresh", show=True, priority=True),
        Binding("O", "open_search", "Search", show=True, priority=True),
        Binding("L", "open_log", "Log", show=True),
        Binding("C", "open_coverage", "Coverage", show=True),
        Binding("P", "open_plugin", "Plugin", show=False),
    ]

    data_test_tree: reactive[dict] = reactive({}, init=False)
    counter_total_tests: reactive[int] = reactive(0, init=False)
    plugin_option_dict: reactive[dict] = reactive({}, init=False)
    selected_options_dict: reactive[dict] = reactive({}, init=False)

    filter: reactive[dict] = reactive(
        {
            "show_favourites": True,
            "show_failed": True,
            "show_skipped": True,
            "show_passed": True,
            "excluded_markers": {},
        },
        init=False,
    )
    test_results_ready: reactive[bool] = reactive(False, init=False)
    tests_running: reactive[bool] = reactive(False, init=False)
    file_watcher: reactive[bool] = reactive(False, init=False)
    markers: reactive[list[str]] = reactive(list)
    DEV: bool = False
    """Show The Log Collapsibles"""

    def __init__(
        self,
        test_path: Path | None = None,
        host: str | None = None,
        port: int | None = None,
        *args,
        **kwargs,
    ):
        self.host = host or os.environ.get("AYU_HOST") or WEB_SOCKET_HOST
        self.port = port or int(os.environ.get("AYU_PORT", 0)) or WEB_SOCKET_PORT
        self.dispatcher = None
        self.test_path = test_path
        super().__init__(*args, **kwargs)

    def compose(self):
        yield Header()
        yield Footer(show_command_palette=False)
        outcome_log = Log(id="log_outcome")
        outcome_log.border_title = "Outcome"
        report_log = Log(id="log_report")
        report_log.border_title = "Report"
        collection_log = Log(id="log_collection")
        collection_log.border_title = "Collection"
        debug_log = Log(id="log_debug")
        debug_log.border_title = "Debug"
        yield LogViewer()
        yield CoverageExplorer()
        with Horizontal():
            with Vertical(id="vertical_test_tree"):
                yield TestTree(label="Tests", id="testtree").data_bind(
                    filter=AyuApp.filter,
                    filtered_data_test_tree=AyuApp.data_test_tree,
                    filtered_counter_total_tests=AyuApp.counter_total_tests,
                )
                yield TreeFilter().data_bind(
                    test_results_ready=AyuApp.test_results_ready, markers=AyuApp.markers
                )
            with Vertical():
                yield DetailView()
                if self.DEV:
                    with Collapsible(title="Outcome", collapsed=True):
                        yield outcome_log
                    with Collapsible(title="Report", collapsed=True):
                        yield report_log
                    with Collapsible(title="Collection", collapsed=True):
                        yield collection_log
                    with Collapsible(title="Debug", collapsed=False):
                        yield debug_log
                yield ButtonPanel().data_bind(
                    tests_running=AyuApp.tests_running, file_watcher=AyuApp.file_watcher
                )

    async def on_load(self):
        self.start_socket()

        # Watcher
        # self.run_tests_on_change()

    @work(
        exclusive=True,
        description="Watches files for changes to automatically rerun the changed file",
        group="Watcher",
    )
    async def start_tests_on_change_worker(self):
        path_to_watch = self.test_path or Path("tests")
        async for changes in awatch(path_to_watch, watch_filter=PythonFilter()):
            if not self.tests_running:
                self.notify("Files have changed", severity="information")
                for change in changes:
                    change_mode, path = change
                    self.action_run_tests(tests_to_run=Path(path))
            else:
                self.notify(
                    title="Warning", message="Tests running already", severity="warning"
                )

    def on_mount(self):
        # For Developing/Debugging
        if self.DEV:
            self.dispatcher.register_handler(
                event_type=EventType.OUTCOME,
                handler=lambda msg: self.update_outcome_log(msg),
            )
            self.dispatcher.register_handler(
                event_type=EventType.COVERAGE,
                handler=lambda msg: self.update_debug_log(msg),
            )
            self.dispatcher.register_handler(
                event_type=EventType.DEBUG,
                handler=lambda msg: self.update_debug_log(msg),
            )
            self.dispatcher.register_handler(
                event_type=EventType.REPORT,
                handler=lambda msg: self.update_report_log(msg),
            )

        self.dispatcher.register_handler(
            event_type=EventType.PLUGIN,
            handler=lambda msg: self.update_plugin_dict(msg),
        )
        self.dispatcher.register_handler(
            event_type=EventType.OPTIONS,
            handler=lambda msg: self.update_selected_options(msg),
        )

        self.dispatcher.register_handler(
            event_type=EventType.COLLECTION,
            handler=lambda data: self.update_app_data(data),
        )
        self.query_one(TestTree).focus()

        self.collect_initial_plugins()
        self.collect_initial_test_tree()

    def update_app_data(self, data):
        self.data_test_tree = data["tree"]
        self.counter_total_tests = data["meta"]["test_count"]
        self.markers = data["meta"]["markers"]

    def update_plugin_dict(self, data):
        self.plugin_option_dict = data["plugin_dict"]

    def update_selected_options(self, data):
        self.selected_options_dict.update(data["option_dict"])

    # Get initial Data
    @work(
        exclusive=True,
        group="Collector",
        description="Executes `pytest --co` and collects tests",
    )
    async def collect_initial_test_tree(self):
        command = build_command(
            plugins=None,
            tests_to_run=self.test_path,
            pytest_options=["--co"],
        )
        await run_test_collection(command=command)

    @work(
        exclusive=True,
        group="Plugin",
        description="Executes `pytest --help` and collect Plugin Infos",
    )
    async def collect_initial_plugins(self):
        command = build_command(
            plugins=None,
            tests_to_run=self.test_path,
            pytest_options=["--help"],
        )
        await run_plugin_collection(command=command)

    @work(exclusive=True, description="Keeps the websocket alive", group="Websocket")
    async def start_socket(self):
        self.dispatcher = EventDispatcher(host=self.host, port=self.port)
        self.notify(
            f"Websocket Started at\n[orange]{self.host}:{self.port}[/]", timeout=1
        )
        try:
            await self.dispatcher.start()
        except OSError as e:
            self.log.error(e)
            pass

    def on_key(self, event: Key):
        if event.key == "w":
            for worker in self.workers:
                self.notify(f"{worker}", markup=False)

    @on(Button.Pressed, ".filter-button")
    def update_test_tree_filter(self, event: Button.Pressed):
        button_id_part = event.button.id.split("_")[-1]
        filter_state = event.button.filter_is_active
        self.filter[f"show_{button_id_part}"] = filter_state
        self.mutate_reactive(AyuApp.filter)

    def reset_filters(self):
        for btn in self.query(".filter-button"):
            btn.filter_is_active = True
        self.filter = {
            "show_favourites": True,
            "show_failed": True,
            "show_skipped": True,
            "show_passed": True,
        }
        self.mutate_reactive(AyuApp.filter)

    @on(Tag.Hovered)
    @on(Tag.Focused)
    @on(Tag.Selected)
    def hightlight_test_tree(self, event: Tag.Hovered | Tag.Focused | Tag.Selected):
        self.query_one(TestTree).highlight_marker_rows(marker=event.tag.value)

    @on(MarkersFilter.Marked)
    def favourite_tests_from_tags(self, event: MarkersFilter.Marked):
        self.query_one(TestTree).mark_test_as_fav_from_markers(marker=event.current_tag)

    @on(ModalSearch.Marked)
    def favourite_tests_from_search(self, event: ModalSearch.Marked):
        self.query_one(TestTree).action_mark_test_as_fav_from_search(
            nodeid=event.nodeid
        )

    @on(Tree.NodeHighlighted)
    def update_test_preview(self, event: Tree.NodeHighlighted):
        detail_view = self.query_one(DetailView)
        detail_view.file_path_to_preview = Path(event.node.data["path"])
        if event.node.data["type"] in [
            NodeType.FUNCTION,
            NodeType.COROUTINE,
            NodeType.CLASS,
        ]:
            detail_view.test_start_line_no = event.node.data["lineno"]
        else:
            detail_view.test_start_line_no = -1

        self.query_one(ToggleRule).test_result = event.node.data["status"]
        self.query_one(TestResultDetails).selected_node_id = event.node.data["nodeid"]

    @on(Button.Pressed, "#button_watcher")
    def toggle_file_watcher(self, event: Button.Pressed):
        self.file_watcher = not self.file_watcher

    @on(Button.Pressed, "#button_plugins")
    def open_plugin_screen(self, event: Button.Pressed):
        self.action_open_plugin()

    @on(Button.Pressed, "#button_coverage")
    def toggle_coverage_explorer(self, event: Button.Pressed):
        self.action_open_coverage()

    @on(Button.Pressed, "#button_log")
    def toggle_log_viewer(self, event: Button.Pressed):
        self.action_open_log()

    @on(Button.Pressed, "#button_run")
    def toggle_test_run(self, event: Button.Pressed):
        if self.query_one(TestTree).marked_tests:
            self.action_run_marked_tests()
        else:
            self.action_run_tests()

    # Actions
    def action_open_plugin(self):
        self.push_screen(
            ModalPlugin().data_bind(
                selected_options_dict=AyuApp.selected_options_dict,
                plugin_option_dict=AyuApp.plugin_option_dict,
            )
        )

    def action_show_details(self):
        self.query_one(DetailView).toggle()
        self.query_one(TreeFilter).toggle()

    def action_open_log(self):
        self.query_one(LogViewer).display = not self.query_one(LogViewer).display

    def action_open_coverage(self):
        cov_explorer = self.query_one(CoverageExplorer)
        cov_explorer.disabled = cov_explorer.display
        cov_explorer.display = not cov_explorer.display
        if cov_explorer.display:
            cov_explorer.query_one("#table_coverage").focus()
        else:
            self.query_one(TestTree).focus()

    @work(
        thread=True,
        group="Test Runner",
        description="runs all tests under a specific path",
    )
    async def action_run_tests(self, tests_to_run: Path | None = None):
        self.tests_running = True
        self.reset_filters()
        # Log Runner Output
        if not tests_to_run:
            tests_to_run = self.test_path

        command = build_command(
            plugins=None,
            tests_to_run=tests_to_run,
        )
        runner = await run_all_tests(command=command)
        while runner:
            if runner.returncode is not None:
                break
            output_line = await runner.stdout.readline()
            decoded_line = remove_ansi_escapes(output_line.decode())
            self.call_from_thread(self.query_one(OutputLog).write_line, decoded_line)
        # Log Runner End
        self.tests_running = False
        self.test_results_ready = True

    @work(thread=True, group="Test Runner", description="runs marked tests only")
    async def action_run_marked_tests(self):
        self.tests_running = True
        self.reset_filters()

        command = build_command(
            plugins=None,
            tests_to_run=self.query_one(TestTree).marked_tests,
        )
        runner = await run_all_tests(command=command)
        while runner:
            if runner.returncode is not None:
                break
            output_line = await runner.stdout.readline()
            decoded_line = remove_ansi_escapes(output_line.decode())
            self.call_from_thread(self.query_one(OutputLog).write_line, decoded_line)

        self.tests_running = False
        self.test_results_ready = True

    def action_refresh(self):
        self.collect_initial_test_tree()
        self.test_results_ready = False

    def action_clear_test_results(self):
        self.test_results_ready = False
        self.query_one(TestTree).reset_test_results()
        for log in self.query(Log):
            log.clear()

    def action_open_search(self):
        def select_searched_nodeid(nodeid: str | None):
            if nodeid:
                node = self.query_one(TestTree).get_node_by_nodeid(nodeid=nodeid)
                self.query_one(TestTree).select_node(node=node)

        self.push_screen(ModalSearch(), callback=select_searched_nodeid)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # on app startup widget is not mounted yet so
        # try except is needed
        try:
            if action == "run_tests":
                if self.query_one(TestTree).marked_tests:
                    return False
            if action == "run_marked_tests":
                if not self.query_one(TestTree).marked_tests:
                    return False
        except NoMatches:
            return True
        return True

    def update_outcome_log(self, msg):
        self.query_one("#log_outcome", Log).write_line(f"{msg}")

    def update_report_log(self, msg):
        self.query_one("#log_report", Log).write_line(f"{msg}")

    def update_debug_log(self, msg):
        self.query_one("#log_debug", Log).write_line(f"{msg}")

    def watch_file_watcher(self):
        if self.file_watcher:
            self.start_tests_on_change_worker()
        else:
            self.workers.cancel_group(node=self, group="Watcher")

    def watch_tests_running(self):
        if self.tests_running:
            self.notify("Started Tests", timeout=2)

    # Watchers
    # def watch_data_test_tree(self):
    #     self.query_one("#log_collection", Log).write_line(f"{self.data_test_tree}")


# https://watchfiles.helpmanual.io
