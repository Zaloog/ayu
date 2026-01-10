from pathlib import Path
from dataclasses import dataclass

from ayu.utils import ayu_is_run_as_tool, project_is_uv_managed


@dataclass
class Plugin:
    name: str
    is_installed: bool
    options: list[str]
    version: str = ""


def build_command(
    plugins: list[Plugin] | None = None,
    tests_to_run: Path | list[str] | None = None,
    pytest_options: list[str] | None = None,
) -> str:
    command_parts = []

    if project_is_uv_managed():
        # is ayu installed in the current project or run as tool
        is_tool = ayu_is_run_as_tool()

        # install ayu on the fly, if ayu is not installed in the project itself
        substring_uv = "uv run --with ayu" if is_tool else "uv run"
        command_parts.append(substring_uv)

        # if plugins are declared with options, but are not installed in the project install them on the fly
        if plugins:
            substring_plugins_to_install = " ".join(
                [f"--with {plugin.name}" for plugin in plugins if not plugin.is_installed]
            )
            command_parts.append(substring_plugins_to_install)

    # pytest call here
    command_parts.append("pytest")

    # plugin options
    if plugins:
        substring_plugin_options = " ".join(
            [option for plugin in plugins for option in plugin.options]
        )
        command_parts.append(substring_plugin_options)

    # plugin options
    if pytest_options:
        substring_pytest_options = " ".join(pytest_options)
        command_parts.append(substring_pytest_options)
    # wrap tests in quotes to prevent errors when parametrize
    # args include spaces
    if tests_to_run:
        if isinstance(tests_to_run, Path):
            substring_tests_to_run = tests_to_run.as_posix()
        else:
            substring_tests_to_run = " ".join([f'"{test}"' for test in tests_to_run])
        command_parts.append(substring_tests_to_run)

    # only join non empty substrings
    return " ".join([substring for substring in command_parts if substring])
