"""Policy engine.

Decides whether launching a given application should be blocked.

Policy kinds (per application and per group):

* ``always``    — locked whenever the monitor is active.
* ``time``      — locked outside an allowed window (e.g. allow 07:00–20:00).
* ``schedule``  — locked on configured weekdays with a per-day start/end window.
* ``none``      — not protected (no block).

Runtime modifiers:
* ``temp_unlock``  — a UTC epoch until which the app is allowed regardless of
  policy. Used by “Unlock for N minutes”.
* ``session_unlock`` — unlocked until the app process exits / reboots
  (the monitor resets these on launch).

``PolicyEvaluator`` is deterministic, pure and unit-testable: given a policy
record and a ``datetime`` it returns True (block) or False (allow).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


# --------------------------------------------------------------------------- #
# Policy record types
# --------------------------------------------------------------------------- #
@dataclass
class ScheduleWindow:
    """One allowed window for a schedule entry."""

    start_hour: int = 0
    start_minute: int = 0
    end_hour: int = 23
    end_minute: int = 59

    def allows(self, dt: datetime) -> bool:
        start = self.start_hour * 60 + self.start_minute
        end = self.end_hour * 60 + self.end_minute
        now = dt.hour * 60 + dt.minute
        if start <= end:
            return start <= now <= end
        # Overnight window (e.g. 22:00 → 07:00).
        return now >= start or now <= end

    def to_dict(self) -> dict:
        return {
            "start_hour": self.start_hour,
            "start_minute": self.start_minute,
            "end_hour": self.end_hour,
            "end_minute": self.end_minute,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "ScheduleWindow":
        data = data or {}
        return cls(
            start_hour=int(data.get("start_hour", 0)),
            start_minute=int(data.get("start_minute", 0)),
            end_hour=int(data.get("end_hour", 23)),
            end_minute=int(data.get("end_minute", 59)),
        )


@dataclass
class PolicyRecord:
    """A complete protection policy for one application or group."""

    kind: str = "none"  # none | always | time | schedule
    allow_start: str = "07:00"  # used by ``time``
    allow_end: str = "20:00"    # used by ``time``
    schedule: dict = field(default_factory=dict)  # { "Mon": {start_hour..}, ... }
    # Runtime state (not persisted in policy JSON):
    temporary_until: float = 0.0          # epoch seconds
    session_unlocked: bool = False

    def is_protected(self) -> bool:
        return self.kind in ("always", "time", "schedule")

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "allow_start": self.allow_start,
            "allow_end": self.allow_end,
            "schedule": self.schedule,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "PolicyRecord":
        data = data or {}
        return cls(
            kind=data.get("kind", "none"),
            allow_start=data.get("allow_start", "07:00"),
            allow_end=data.get("allow_end", "20:00"),
            schedule=data.get("schedule", {}),
        )

    # -- schedule helpers ------------------------------------------------ #
    @staticmethod
    def _parse(hhmm: str) -> tuple[int, int]:
        hh, _, mm = hhmm.partition(":")
        return int(hh or 0), int(mm or 0)

    def _window_for(self, dt: datetime) -> Optional[ScheduleWindow]:
        if self.kind == "time":
            sh, sm = self._parse(self.allow_start)
            eh, em = self._parse(self.allow_end)
            return ScheduleWindow(sh, sm, eh, em)
        if self.kind == "schedule":
            # Use weekday index to avoid locale-dependent strftime("%a").
            # Map 0=Mon .. 6=Sun regardless of system language.
            _keys = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            day = _keys[dt.weekday()]
            entry = self.schedule.get(day)
            if entry is None:
                return None
            return ScheduleWindow.from_dict(entry)
        return None


class PolicyEvaluator:
    """Returns True (→ block) or False (→ allow) for a policy + moment."""

    def __init__(self, now: Optional[datetime] = None):
        self._now = now

    def blocks(self, policy: PolicyRecord, at: Optional[datetime] = None) -> bool:
        dt = at or self._now or datetime.now()
        # Temporary unlock overrides every policy.
        if policy.temporary_until and policy.temporary_until > time.time():
            return False
        if policy.session_unlocked:
            return False
        if policy.kind == "none":
            return False
        if policy.kind == "always":
            return True
        window = policy._window_for(dt)
        if window is None:
            return True  # outside any allowed window → blocked
        return not window.allows(dt)


def _coerce_schedule(value) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def blocks_app(app: dict, evaluator: PolicyEvaluator, groups: list[dict] | None = None) -> bool:
    """Evaluate an app row from the DB (including any group policies).

    The *most restrictive* policy wins: if either the app or any of its groups
    blocks at this moment, the app is blocked.
    """
    own = PolicyRecord.from_dict({"kind": app.get("policy", "none"),
                                  "allow_start": app.get("allow_start", "07:00"),
                                  "allow_end": app.get("allow_end", "20:00"),
                                  "schedule": _coerce_schedule(app.get("schedule_json"))})
    temp_unlock = app.get("temp_unlock") or 0
    own.temporary_until = float(temp_unlock)
    now_epoch = time.time()
    if temp_unlock and now_epoch < temp_unlock:
        return False
    if evaluator.blocks(own):
        return True
    for group in groups or []:
        sj = _coerce_schedule(group.get("schedule_json"))
        # Groups store time-window times inside schedule_json when kind=="time"
        # (e.g. {"__allow_start":"07:00","__allow_end":"20:00", ...}) or as
        # dedicated columns if the schema was migrated. Hard-coded fallback kept
        # only for legacy rows.
        g_allow_start = group.get("allow_start") or sj.get("__allow_start") or sj.get("allow_start") or "07:00"
        g_allow_end = group.get("allow_end") or sj.get("__allow_end") or sj.get("allow_end") or "20:00"
        # Remove the time-window keys from the schedule dict before evaluation.
        g_schedule = {k: v for k, v in sj.items() if not k.startswith("__") and k not in ("allow_start", "allow_end")}
        gpolicy = PolicyRecord.from_dict({"kind": group.get("policy", "none"),
                                          "allow_start": g_allow_start, "allow_end": g_allow_end,
                                          "schedule": g_schedule})
        if evaluator.blocks(gpolicy):
            return True
    return False


def convert_schedule(days, start_hour, start_minute, end_hour, end_minute) -> dict:
    """Build a schedule dict keyed by weekday (Mon..Sun) from UI inputs.

    Days: list of long weekday names or three-letter names.
    """
    names = {"Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed", "Thursday": "Thu",
             "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"}
    out = {}
    for day in days:
        key = names.get(day, day[:3])
        out[key] = {
            "start_hour": start_hour,
            "start_minute": start_minute,
            "end_hour": end_hour,
            "end_minute": end_minute,
        }
    return out


WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]