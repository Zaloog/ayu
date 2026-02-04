[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![PyPI-Server](https://img.shields.io/pypi/v/ayu.svg)](https://pypi.org/project/ayu/)
[![Pyversions](https://img.shields.io/pypi/pyversions/ayu.svg)](https://pypi.python.org/pypi/ayu)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/ayu)](https://pepy.tech/project/ayu)
[![Coverage Status](https://coveralls.io/repos/github/Zaloog/ayu/badge.svg?branch=main)](https://coveralls.io/github/Zaloog/ayu?branch=main)

# ayu
ayu is a TUI and pytest-plugin, which allows you to run your pytest tests in a more interactive
fashion in your terminal.


# Features
## Main Screen
![preview](https://raw.githubusercontent.com/Zaloog/ayu/main/images/main_screen.png)
- Explore your Test tree
- Mark tests to run, via the test-tree, markers or the search function
- View and filter test results and debug errors

## Coverage Viewer
![coverage](https://raw.githubusercontent.com/Zaloog/ayu/main/images/coverage_screen.png)
- View your code coverage (first view is just based on a `--collect-only`)

## Plugin Explorer
> Currently just exploratory, changes made here are not persisted to your pytest config

![plugin](https://raw.githubusercontent.com/Zaloog/ayu/main/images/plugin_screen.png)
- View your plugin options and discover new plugins

## Log
![log](https://raw.githubusercontent.com/Zaloog/ayu/main/images/log_screen.png)
- Shows the console output, that would normally be written into the terminal

## File Watcher
If toggled, ayu utilizes [watchfiles], to detect changes in the directory you declared when executing ayu (default: `tests`).
After a change is detected, a notification is shown and all tests under the specific file will be run automatically.

## How does it work
The application starts a local websocket server at `localhost:1337` and the plugin sends data about
collected tests/plugins/results to the app.
The host and port can be customized with the following environment variables

It utilizes [uv] in the background to run [pytest] commands.
Concrete it runs `uv run --with ayu pytest [PYTEST-OPTION]` to utilize your python environment and installs the
plugin temporary on the fly to send the data to the TUI, without changing your local environment
or adding dependencies to your project.

```bash
AYU_HOST=localhost
AYU_PORT=1337
```

# Requirements & Usage
## Requirements
ayu needs your tests be discoverable by pytest. It works best when your project is managed by uv. Using it without uv may work, but is not supported.

## Usage
To discover all your tests under `tests`

```bash
uvx ayu
```

To discover all your tests under a specific directory
```bash
uvx ayu <PATH/TO/DIR>
```

# Feedback and Issues
Feel free to reach out and share your feedback, or open an [Issue],
if something doesnt work as expected.
Also check the [Changelog] for new updates.


<!-- Repo Links -->
[Changelog]: https://github.com/Zaloog/ayu/blob/main/CHANGELOG.md
[Issue]: https://github.com/Zaloog/ayu/issues

<!-- Python Package Links -->
[uv]: https://docs.astral.sh/uv
[pytest]: https://docs.pytest.org/en/stable/
[watchfiles]: https://watchfiles.helpmanual.io
