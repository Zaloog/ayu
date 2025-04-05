from enum import Enum


class NodeType(str, Enum):
    DIR = "DIR"
    MODULE = "MODULE"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"


class EventType(str, Enum):
    COLLECTION = "COLLECTION"
    OUTCOME = "OUTCOME"
    REPORT = "REPORT"
