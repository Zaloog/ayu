from types import FunctionType, NoneType
from typing import Any
from collections import defaultdict
import os
import shutil
import re
from enum import Enum
from pathlib import Path
import subprocess

import asyncio
from pytest import Config, OptionGroup
from pytest import Item, Class, Function
from _pytest.nodes import Node

from ayu.constants import WEB_SOCKET_PORT, WEB_SOCKET_HOST


class NodeType(str, Enum):
    DIR = "DIR"
    MODULE = "MODULE"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    COROUTINE = "COROUTINE"


class EventType(str, Enum):
    COLLECTION = "COLLECTION"
    SCHEDULED = "SCHEDULED"
    OUTCOME = "OUTCOME"
    REPORT = "REPORT"
    COVERAGE = "COVERAGE"
    PLUGIN = "PLUGIN"
    OPTIONS = "OPTIONS"
    DEBUG = "DEBUG"


class TestOutcome(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    QUEUED = "QUEUED"
    # handle those
    XFAILED = "XFAILED"
    XPASSED = "XPASSED"
    ERROR = "XPASSED"


class OptionType(str, Enum):
    INT = "INT"
    LIST = "LIST"
    STR = "STR"
    BOOL = "BOOL"
    SELECTION = "SELECTION"
    UNKNOWN = "UNKNOWN"


async def run_plugin_collection(command: str):
    """Collect All Tests without running them"""

    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    await process.wait()


async def run_test_collection(command: str):
    """Collect All Tests without running them"""

    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    await process.wait()


async def run_all_tests(command: str):
    """Run all selected tests"""

    return await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )


def get_nice_tooltip(node_data: dict) -> str | None:
    tooltip_str = ""
    # tooltip_str = f"{node_data['name'].replace("[", "\["):^20}\n"
    # tooltip_str += f"[red strike]{node_data['name'].replace('[', '\['):^20}[/]\n"
    #
    # status = node_data["status"].replace("[", "\[")
    # tooltip_str += f"\n[yellow]{status}[/]\n\n"
    return tooltip_str


def get_preview_test(file_path: str, start_line_no: int) -> str:
    """Read the test file from nodeid and use the linenumber
    and some rules to display the test function"""
    with open(Path(file_path), "r") as file:
        file_lines = file.readlines()
        last_line_is_blank = False
        end_line_no = None
        for line_no, line in enumerate(file_lines[start_line_no:], start=start_line_no):
            if not line.strip():
                last_line_is_blank = True
                continue
            if (
                line.strip().startswith(("def ", "class ", "async def ", "@"))
                and last_line_is_blank
            ):
                end_line_no = line_no - 1
                break
            last_line_is_blank = False
        return "".join(file_lines[start_line_no:end_line_no]).rstrip()


def get_ayu_websocket_host_port() -> tuple[str, int]:
    host: str = os.environ.get("AYU_HOST", WEB_SOCKET_HOST)
    port: int = int(os.environ.get("AYU_PORT", WEB_SOCKET_PORT))
    return host, port


def remove_ansi_escapes(string_to_remove: str) -> str:
    """Remove ansi escaped strings from colored pytest output"""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", string_to_remove)


def uv_is_installed():
    if shutil.which("uv"):
        return True
    return False


def project_is_uv_managed():
    toml_path = Path.cwd() / "pyproject.toml"
    return toml_path.exists()


def ayu_is_run_as_tool():
    result = subprocess.run(
        "uv tree --package ayu".split(), capture_output=True, text=True
    )
    if result.stdout:
        return False
    return True


def build_dict_tree(items: list[Item]) -> dict:
    markers = set()

    def create_node(node: Node) -> dict[Any, Any]:
        markers.update([mark.name for mark in node.own_markers])
        return test_node_to_dict(node=node)

    def add_node(node_list: list[Node], sub_tree: dict):
        if not node_list:
            return

        # take root node
        current_node = node_list.pop(0)
        node_dict = create_node(node=current_node)

        existing_node = next(
            (
                node
                for node in sub_tree["children"]
                if node["nodeid"] == current_node.nodeid
            ),
            None,
        )

        if existing_node is None:
            sub_tree["children"].append(node_dict)
            existing_node = node_dict

        add_node(
            node_list=node_list,
            sub_tree=existing_node,
        )

    tree: dict[Any, Any] = {}
    root = items[0].listchain()[1]
    tree[root.name] = create_node(node=root)

    for item in items:
        # gets all parents except session
        parts_to_collect = item.listchain()[1:]
        add_node(node_list=parts_to_collect[1:], sub_tree=tree[root.name])

    return {"tree": tree, "meta": {"test_count": len(items), "markers": list(markers)}}


def get_coverage_data(coverage_file=".coverage"):
    import coverage

    cov = coverage.Coverage(data_file=coverage_file)
    cov.load()

    report_dict = {}

    all_files = cov.get_data().measured_files()
    for file_path in sorted(all_files):
        file_data = cov.analysis2(file_path)
        # analysis2 returns: (0:filename, 1:statements, 2:excluded, 3:missing, 4:partial)
        total_statements = len(file_data[1])  # All statements
        missing_statements = len(file_data[3])  # Uncovered statements
        coverage_percent = (
            (total_statements - missing_statements) / total_statements * 100
            if total_statements > 0
            else 0
        )

        # Store data for this file
        displayed_path = Path(file_path).relative_to(Path.cwd()).as_posix()
        report_dict[displayed_path] = {
            "n_statements": total_statements,
            "n_missed": missing_statements,
            "percent_covered": round(coverage_percent, 2),
            "lines_missing": file_data[3],  # List of uncovered line numbers
        }

    return report_dict


def test_node_to_dict(node: Node) -> dict[str, Any]:
    return {
        "name": node.name,
        "nodeid": node.nodeid,
        "markers": [mark.name for mark in node.own_markers],
        "path": node.path.as_posix(),
        "lineno": node.reportinfo()[1]
        if isinstance(node, Class)
        else (node.location[1] if isinstance(node, Function) else 0),
        "parent_name": node.parent.name if node.parent else None,
        "parent_type": type(node.parent).__name__.upper() if node.parent else None,
        "type": type(node).__name__.upper(),
        "favourite": False,
        "status": "",
        "children": [],
    }


def build_bar(percentage: float) -> str:
    SEGS = ["▉", "▊", "▋", "▌", "▍", "▎", "▏", ""]
    tens = int(percentage // 10)
    # can stay float cause we dont multiply it with strings
    rest = percentage - tens * 10
    not_tens = int((100 - percentage) // 10)

    tens_bar = f"[green on green]{tens * ' '}[/]"

    if rest == 0:
        rest_bar = ""
    elif rest < 2:
        rest_bar = f"[green on red]{SEGS[5]}[/]"
    elif rest < 4:
        rest_bar = f"[green on red]{SEGS[3]}[/]"
    elif rest < 6:
        rest_bar = f"[green on red]{SEGS[2]}[/]"
    elif rest < 8:
        rest_bar = f"[green on red]{SEGS[1]}[/]"
    elif rest < 10:
        rest_bar = f"[green on red]{SEGS[0]}[/]"

    not_tens_bar = f"[on red]{not_tens * ' '}[/]"
    return tens_bar + rest_bar + not_tens_bar


def build_plugin_dict(conf: Config) -> dict:
    # from pprint import pprint

    plugin_infos = sorted(
        set(
            (conf.pluginmanager.get_name(p), dist.version)
            for p, dist in conf.pluginmanager.list_plugin_distinfo()
        )
    )

    all_plugins_dict: dict[str, dict] = defaultdict(dict)
    for plugin_name, version in plugin_infos:
        clean_name = (
            plugin_name[7:] if plugin_name.startswith("pytest") else plugin_name
        )
        plugin_dict = {}
        plugin_group = conf._parser.getgroup(clean_name)
        group_name = plugin_group.name
        group_description = getattr(plugin_group, "description", "No Description")
        group_options = plugin_group.options
        if not group_options:
            continue
        else:
            group_option_list = []
            for option in group_options:
                option_dict = get_plugin_option_dict(option=option)
                group_option_list.append(option_dict)

        plugin_dict["name"] = group_name
        plugin_dict["version"] = version
        plugin_dict["description"] = group_description
        plugin_dict["options"] = group_option_list

        all_plugins_dict[plugin_name] = plugin_dict

    # Remove Later
    # from pprint import pprint
    # pprint(all_plugins_dict['asyncio'], sort_dicts=False)
    return all_plugins_dict


def get_plugin_option_dict(option: OptionGroup) -> dict[str, Any]:
    option_names = option.names()
    option_attrs = option.attrs()
    option_default = option_attrs.get("default")
    option_help = option_attrs.get("help")
    # set type as 'None' if type is desclared as a function e.g. for validation
    option_type = infer_option_type(option_attributes=option_attrs)
    option_choices = option_attrs.get("choices")
    option_destination = option_attrs.get("dest")

    option_dict = {}

    # handle enums, cause they are not serializable
    if isinstance(option_default, Enum):
        option_default = option_default.value
        option_choices = [choice.value for choice in option_choices]

    option_dict["names"] = option_names
    option_dict["default"] = option_default
    option_dict["help"] = option_help
    option_dict["type"] = option_type
    option_dict["choices"] = option_choices
    option_dict["dest"] = option_destination
    # option_dict["attrs"] = option_attrs

    return option_dict


def infer_option_type(option_attributes: dict) -> OptionType:
    option_default = option_attributes.get("default")
    option_type = option_attributes.get(
        "type", type(option_default) if option_default is not None else None
    )

    if isinstance(option_type, (FunctionType, NoneType)):
        return OptionType.STR
    elif option_type is bool:
        return OptionType.BOOL
    elif option_attributes.get("choices"):
        return OptionType.SELECTION
    elif option_type is str:
        return OptionType.STR
    elif option_type is list:
        return OptionType.LIST
    elif option_type is int:
        return OptionType.INT
    else:
        return OptionType.UNKNOWN

    return option_type


def get_pytest_current_options(conf: Config) -> dict:
    def handle_enums(value: Enum | Any):
        if isinstance(value, Enum):
            return value.value
        return value

    return {option: handle_enums(value) for option, value in conf.option._get_kwargs()}
