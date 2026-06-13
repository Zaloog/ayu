from textual.binding import Binding
from textual.message import Message
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Button, Rule

from rich.text import Text
from textual_slidecontainer import SlideContainer
from textual_tags import Tags, Tag, TagInput


class TreeFilter(SlideContainer):
    test_results_ready: reactive[bool] = reactive(False, init=False)
    markers: reactive[list[str]] = reactive([], init=False)

    def __init__(self, *args, **kwargs):
        super().__init__(
            slide_direction="down",
            floating=False,
            start_open=False,
            duration=0.5,
            *args,
            **kwargs,
        )

    def toggle(self) -> None:
        if not self.state:
            self.display = True
            self.call_after_refresh(self.open)
        else:
            self.close()

    def compose(self):
        yield MarkersFilter(tag_values=self.markers, show_x=True).data_bind(
            TreeFilter.markers
        )
        yield Rule()
        yield ResultFilter(id="horizontal_result_filter").data_bind(
            test_results_ready=TreeFilter.test_results_ready
        )


class ResultFilter(Horizontal):
    test_results_ready: reactive[bool] = reactive(False, init=False)

    def watch_test_results_ready(self):
        if not self.test_results_ready:
            self.border_title = Text.from_markup("No Tests have been run yet")
        else:
            self.border_title = Text.from_markup(
                ":magnifying_glass_tilted_right: Test Result Filter (click to toggle)"
            )
        display_style = "block" if self.test_results_ready else "none"
        self.query_children(".filter-button").set_styles(f"display:{display_style};")
        self.query_children(Button).last().display = not self.test_results_ready

    def compose(self):
        yield FilterButton(
            label=Text.from_markup("Marked: :star:"),
            id="button_filter_favourites",
            classes="filter-button",
        )
        yield FilterButton(
            label=Text.from_markup("Passed: :white_check_mark:"),
            id="button_filter_passed",
            classes="filter-button",
        )
        yield FilterButton(
            label=Text.from_markup("Failed: :x:"),
            id="button_filter_failed",
            classes="filter-button",
        )
        yield FilterButton(
            label=Text.from_markup("Skipped: [on yellow]:next_track_button: [/]"),
            id="button_filter_skipped",
            classes="filter-button",
        )
        yield Button(
            "Result Filter is available once tests are run",
            variant="primary",
            id="button_info",
        )


class FilterButton(Button):
    """Button for filtering the TestTree"""

    filter_is_active: reactive[bool] = reactive(True)

    def on_button_pressed(self):
        self.filter_is_active = not self.filter_is_active

    def watch_filter_is_active(self):
        self.variant = "success" if self.filter_is_active else "error"


class MarkersFilter(Tags):
    markers: reactive[list[str]] = reactive([])
    BINDINGS = [Binding("f", "mark_tests_with_markers", "⭐ Mark")]

    class Marked(Message):
        def __init__(self, current_tag: Tag) -> None:
            self.current_tag = current_tag
            super().__init__()

        @property
        def control(self):
            return self.current_tag

    async def watch_markers(self):
        self.query_one("#input_tag", TagInput).placeholder = "Select markers..."
        self.tag_values = set(self.markers)
        await self.query(Tag).remove()
        self.call_later(self._populate_with_tags)

    def action_mark_tests_with_markers(self):
        current_tag = self.app.focused.value
        self.post_message(self.Marked(current_tag=current_tag))

        # self.notify(f'unselected: {self.unselected_tags}')
        # self.selected_tags = set(self.markers)
        # await super().watch_tag_values()
        # super().watch_allow_new_tags()
