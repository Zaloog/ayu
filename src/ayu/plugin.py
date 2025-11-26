import os
import asyncio
import pytest
from pytest import Config, TestReport, Session, Parser
from _pytest.terminal import TerminalReporter, WarningReport

from ayu.event_dispatcher import send_event, check_connection
from ayu.classes.event import Event
from ayu.utils import (
    EventType,
    TestOutcome,
    get_pytest_current_options,
    remove_ansi_escapes,
    build_dict_tree,
    build_plugin_dict,
    get_coverage_data,
)

# import logging
# logging.basicConfig(level=logging.DEBUG)


def pytest_addoption(parser: Parser) -> None:
    group = parser.getgroup("ayu", "interactive pytest interface")
    group.addoption(
        "--disable-ayu",
        "--da",
        action="store_true",
        default=False,
        help="Disable Ayu plugin functionality, i.e. do not send events to websocket",
    )


@pytest.hookimpl(trylast=True)
def pytest_configure(config: Config) -> None:
    if not config.getoption("--disable-ayu"):
        config.pluginmanager.register(Ayu(config))


class Ayu:
    def __init__(self, config: Config):
        self.config = config
        self.connected = False

        if check_connection():
            print("Websocket connected")
            self.connected = True
        else:
            self.connected = False
            print("Websocket not connected")
        self.load_current_options()
        self.load_used_plugin_infos()

    def load_current_options(self):
        if self.connected and self.config.getoption("--help"):
            option_dict = get_pytest_current_options(conf=self.config)
            asyncio.run(
                send_event(
                    event=Event(
                        event_type=EventType.OPTIONS,
                        event_payload={"option_dict": option_dict},
                    )
                )
            )

    def load_used_plugin_infos(self):
        if self.connected and self.config.getoption("--help"):
            plugin_dict = build_plugin_dict(conf=self.config)
            asyncio.run(
                send_event(
                    event=Event(
                        event_type=EventType.PLUGIN,
                        event_payload={"plugin_dict": plugin_dict},
                    )
                )
            )

    # must tryfirst, otherwise collection-only is returning
    @pytest.hookimpl(tryfirst=True)
    def pytest_runtestloop(self, session: Session):
        if self.connected and session.config.getoption("--collect-only"):
            asyncio.run(
                send_event(
                    event=Event(
                        event_type=EventType.DEBUG,
                        event_payload={"test": "test"},
                        # event_payload={"no_items":session.testscollected,"items":f"{session.items}"},
                    )
                )
                # ,debug_mode=True
            )

    # build test tree
    def pytest_collection_finish(self, session: Session):
        if self.connected:
            print("Connected to Ayu")
            if session.config.getoption("--collect-only"):
                tree = build_dict_tree(items=session.items)
                asyncio.run(
                    send_event(
                        event=Event(
                            event_type=EventType.COLLECTION,
                            event_payload=tree,
                        )
                    ),
                )
            else:
                asyncio.run(
                    send_event(
                        event=Event(
                            event_type=EventType.SCHEDULED,
                            event_payload=[item.nodeid for item in session.items],
                        )
                    )
                )
        return

    # gather status updates during run
    def pytest_runtest_logreport(self, report: TestReport):
        if self.config.pluginmanager.hasplugin("xdist") and (
            "PYTEST_XDIST_WORKER" not in os.environ
        ):
            pass
            return

        is_relevant = (report.when == "call") or (
            (report.when == "setup")
            and (report.outcome.upper() in [TestOutcome.FAILED, TestOutcome.SKIPPED])
        )

        if self.connected and is_relevant:
            asyncio.run(
                send_event(
                    event=Event(
                        event_type=EventType.OUTCOME,
                        event_payload={
                            "nodeid": report.nodeid,
                            "outcome": report.outcome.upper(),
                        },
                    )
                )
            )

    # summary after run for each tests
    @pytest.hookimpl(trylast=True)
    def pytest_terminal_summary(self, terminalreporter: TerminalReporter):
        # Debugging
        # from pprint import pprint
        # option_dict = {option:value for option, value in self.config.option._get_kwargs()}
        # pprint(option_dict)

        # Summary part of individual Workers
        if self.config.pluginmanager.hasplugin("xdist") and (
            "PYTEST_XDIST_WORKER" not in os.environ
        ):
            # Needs to run within workers for correct report
            # if pytest-xdist is available
            if self.config.pluginmanager.hasplugin("_cov") and self.connected:
                coverage_dict = get_coverage_data()

                asyncio.run(
                    send_event(
                        event=Event(
                            event_type=EventType.COVERAGE,
                            event_payload={
                                "coverage_dict": coverage_dict,
                            },
                        )
                    )
                )

        else:
            if self.config.pluginmanager.hasplugin("_cov") and self.connected:
                coverage_dict = get_coverage_data()

                asyncio.run(
                    send_event(
                        event=Event(
                            event_type=EventType.COVERAGE,
                            event_payload={
                                "coverage_dict": coverage_dict,
                            },
                        )
                    )
                )

        report_dict = {}
        for outcome, reports in terminalreporter.stats.items():
            # raise Exception(terminalreporter.stats.keys())
            if outcome in ["", "deselected"]:
                continue
            for report in reports:
                # Skip WarningReports
                if isinstance(report, WarningReport):
                    continue

                report_dict[report.nodeid] = {
                    "nodeid": report.nodeid,
                    "when": report.when,
                    "caplog": report.caplog,
                    "longreprtext": remove_ansi_escapes(report.longreprtext),
                    "duration": report.duration,
                    "outcome": report.outcome,
                    "lineno": report.location[1],
                    "otherloc": report.location[2],
                }

        # import json

        if self.connected:
            asyncio.run(
                send_event(
                    event=Event(
                        event_type=EventType.REPORT,
                        event_payload={
                            "report": report_dict,
                        },
                    )
                )
            )
