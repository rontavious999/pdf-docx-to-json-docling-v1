"""
Debug logging utilities for template matching and parsing diagnostics.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MatchEvent:
    title: str
    parsed_key: str
    section: str
    matched_key: Optional[str]
    reason: str
    score: float
    coverage: float


class DebugLogger:
    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.events: List[MatchEvent] = []
        self.near_misses: List[MatchEvent] = []
        self.gates: List[str] = []

    def log(self, ev: MatchEvent):
        if self.enabled:
            self.events.append(ev)

    def log_near(self, ev: MatchEvent):
        if self.enabled:
            self.near_misses.append(ev)

    def gate(self, msg: str):
        if self.enabled:
            self.gates.append(msg)

    def print_summary(self):
        if not self.enabled:
            return
        print("  [debug] template matches:")
        for ev in self.events:
            print(f"    ✓ '{ev.title}' -> {ev.matched_key} ({ev.reason}, score={ev.score:.2f}, cov={ev.coverage:.2f})")
        if self.near_misses:
            print("  [debug] near-misses (score>=0.75 but rejected):")
            for ev in self.near_misses:
                print(f"    ~ '{ev.title}' -> {ev.matched_key or '—'} ({ev.reason}, score={ev.score:.2f}, cov={ev.coverage:.2f})")
        if self.gates:
            print("  [debug] gates:")
            for g in self.gates:
                print(f"    • {g}")
