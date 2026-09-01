"""Persistent authoritative debugger sessions for the RoboASM Web API."""

from collections import OrderedDict, deque
from copy import deepcopy
import secrets
import threading
import time

from runtime_api import prepare_level_execution, validate_run_options

MAX_DEBUG_SESSIONS = 32
DEBUG_SESSION_TTL_SECONDS = 30 * 60
MAX_DEBUG_STEP_CYCLES = 1_000
MAX_DEBUG_HISTORY = 256


class DebugSessionNotFound(KeyError):
    """Raised when a debugger session is missing or has expired."""


class DebugSession:
    """A persistent level + VM instance advanced by authoritative Python steps."""

    def __init__(
        self,
        code,
        level_path,
        optimize=False,
        source_base_dir=None,
        history_limit=MAX_DEBUG_HISTORY,
    ):
        if not isinstance(history_limit, int) or isinstance(history_limit, bool) \
                or history_limit < 1:
            raise ValueError("history_limit must be a positive integer")
        self.optimize = optimize
        self.history_limit = history_limit
        self._history = deque(maxlen=history_limit)
        (
            self.level,
            self.assembler,
            self.instructions,
            self.vm,
        ) = prepare_level_execution(
            code,
            level_path,
            optimize=optimize,
            source_base_dir=source_base_dir,
        )

    def _win_status(self):
        return self.level.check_win(self.vm, self.vm.grid)

    @staticmethod
    def _coord_mapping(entries, value_key='value'):
        return {
            (entry['x'], entry['y']): deepcopy(entry[value_key])
            for entry in entries
        }

    def _restore_checkpoint(self, snapshot):
        """Restore every debugger-visible mutable VM field from a native snapshot."""
        if len(snapshot.get('robots', [])) != len(self.vm.robots):
            raise ValueError("Checkpoint robot count does not match the active VM")

        self.vm.cycles = snapshot['cycles']
        self.vm.halted = bool(snapshot['halted'])

        # Preserve shared-RAM object identity so every robot continues to point
        # at exactly the same dictionary after a rewind.
        self.vm.shared_ram.clear()
        self.vm.shared_ram.update(deepcopy(snapshot.get('ram', {})))
        self.vm.msg_queue = [
            (message['sender_id'], deepcopy(message['value']))
            for message in snapshot.get('messages', [])
        ]
        self.vm.faults = deepcopy(snapshot.get('faults', []))

        for robot, state in zip(self.vm.robots, snapshot['robots']):
            robot.x = state['x']
            robot.y = state['y']
            robot.facing = state['facing']
            robot.inventory = deepcopy(state.get('inventory'))
            robot.registers = dict(state.get('registers', {}))
            robot.flags = dict(state.get('flags', {}))
            robot.stack = list(state.get('stack', []))
            robot.pc = state['pc']
            robot.call_stack = list(state.get('call_stack', []))
            robot.halted = bool(state.get('halted', False))
            robot.last_error = deepcopy(state.get('last_error'))
            robot.ram = self.vm.shared_ram

        grid_state = snapshot.get('grid', {})
        self.vm.grid.items = self._coord_mapping(grid_state.get('items', []))
        self.vm.grid.inboxes = self._coord_mapping(
            grid_state.get('inboxes', []), value_key='queue'
        )
        self.vm.grid.outboxes = self._coord_mapping(
            grid_state.get('outboxes', []), value_key='queue'
        )
        self.vm.grid.open_doors = {
            (entry['x'], entry['y'])
            for entry in grid_state.get('open_doors', [])
        }

    def _remember_checkpoint(self):
        self._history.append(self.vm.snapshot())

    def _normalize_breakpoints(self, breakpoint_lines, breakpoint_robot_id):
        if breakpoint_lines is None:
            lines = set()
        else:
            if not isinstance(breakpoint_lines, (list, tuple, set)):
                raise ValueError("breakpoint_lines must be an array of positive integers")
            lines = set()
            for line in breakpoint_lines:
                if not isinstance(line, int) or isinstance(line, bool) or line < 1:
                    raise ValueError(
                        "breakpoint_lines must contain only positive integers"
                    )
                lines.add(line)

        if not isinstance(breakpoint_robot_id, int) \
                or isinstance(breakpoint_robot_id, bool):
            raise ValueError("breakpoint_robot_id must be an integer")
        if breakpoint_robot_id < 0 or breakpoint_robot_id >= len(self.vm.robots):
            raise ValueError("breakpoint_robot_id does not reference an active robot")
        return lines, breakpoint_robot_id

    def _current_breakpoint(self, breakpoint_lines, breakpoint_robot_id):
        """Return breakpoint metadata if the selected robot is paused before a line."""
        if self.vm.cycles <= 0 or not breakpoint_lines:
            return None
        robot = self.vm.robots[breakpoint_robot_id]
        if robot.halted or robot.pc < 0 or robot.pc >= len(self.instructions):
            return None
        instruction = self.instructions[robot.pc]
        line_num = instruction.get('line_num')
        if line_num not in breakpoint_lines:
            return None
        return {
            'robot_id': breakpoint_robot_id,
            'pc': robot.pc,
            'line_num': line_num,
            'cycle': self.vm.cycles,
        }

    def snapshot(self):
        """Return the current persistent session state and compile metadata."""
        won, message = self._win_status()
        return {
            'won': won,
            'message': message,
            'terminal': bool(won or self.vm.halted),
            'cycles': self.vm.cycles,
            'size': len(self.instructions),
            'optimized': self.optimize,
            'instructions': self.instructions,
            'symbol_table': self.assembler.symbol_table,
            'data_memory': self.assembler.data_memory,
            'history_depth': len(self._history),
            'history_limit': self.history_limit,
            'state': self.vm.snapshot(),
        }

    def _terminal_execution(self, capture_trace=False):
        won, _ = self._win_status()
        result = {
            'cycles_executed': 0,
            'total_cycles': self.vm.cycles,
            'halted': self.vm.halted,
            'stopped_by_condition': bool(won),
            'stopped_by_breakpoint': False,
            'breakpoint': None,
            'limit_reached': False,
            'faults': deepcopy(self.vm.faults),
        }
        if capture_trace:
            result['trace'] = [self.vm.snapshot()]
        return result

    def advance(
        self,
        max_cycles=1,
        capture_trace=False,
        breakpoint_lines=None,
        breakpoint_robot_id=0,
    ):
        """Advance this VM, checkpointing cycles and optionally stopping before a breakpoint."""
        validate_run_options(
            max_cycles=max_cycles,
            capture_trace=capture_trace,
            optimize=self.optimize,
        )
        breakpoint_lines, breakpoint_robot_id = self._normalize_breakpoints(
            breakpoint_lines,
            breakpoint_robot_id,
        )
        won, _ = self._win_status()
        if won or self.vm.halted:
            execution = self._terminal_execution(capture_trace=capture_trace)
            return {
                'execution': execution,
                **self.snapshot(),
            }

        start_cycles = self.vm.cycles
        stopped_by_condition = False
        breakpoint_hit = None
        trace = [self.vm.snapshot()] if capture_trace else None

        while not self.vm.halted and self.vm.cycles - start_cycles < max_cycles:
            breakpoint_hit = self._current_breakpoint(
                breakpoint_lines,
                breakpoint_robot_id,
            )
            if breakpoint_hit is not None:
                break

            self._remember_checkpoint()
            self.vm.step()
            if capture_trace:
                trace.append(self.vm.snapshot())
            if self._win_status()[0]:
                stopped_by_condition = True
                break

        executed = self.vm.cycles - start_cycles
        stopped_by_breakpoint = breakpoint_hit is not None
        execution = {
            'cycles_executed': executed,
            'total_cycles': self.vm.cycles,
            'halted': self.vm.halted,
            'stopped_by_condition': stopped_by_condition,
            'stopped_by_breakpoint': stopped_by_breakpoint,
            'breakpoint': breakpoint_hit,
            'limit_reached': (
                not self.vm.halted
                and not stopped_by_condition
                and not stopped_by_breakpoint
                and executed >= max_cycles
            ),
            'faults': deepcopy(self.vm.faults),
        }
        if capture_trace:
            execution['trace'] = trace
        return {
            'execution': execution,
            **self.snapshot(),
        }

    def rewind(self, cycles=1):
        """Restore up to *cycles* authoritative checkpoints on this timeline."""
        if not isinstance(cycles, int) or isinstance(cycles, bool):
            raise ValueError("rewind cycles must be an integer")
        if cycles < 1 or cycles > MAX_DEBUG_STEP_CYCLES:
            raise ValueError(
                f"rewind cycles must be between 1 and {MAX_DEBUG_STEP_CYCLES}"
            )

        requested = cycles
        rewound = 0
        target = None
        while rewound < requested and self._history:
            target = self._history.pop()
            rewound += 1

        if target is not None:
            self._restore_checkpoint(target)

        return {
            'rewind': {
                'requested_cycles': requested,
                'cycles_rewound': rewound,
                'history_depth': len(self._history),
                'history_limit': self.history_limit,
                'at_history_start': not self._history,
            },
            **self.snapshot(),
        }

    def step(self, cycles=1):
        """Move on the session timeline; negative cycles perform authoritative rewind."""
        if not isinstance(cycles, int) or isinstance(cycles, bool):
            raise ValueError("cycles must be an integer")
        if cycles == 0 or abs(cycles) > MAX_DEBUG_STEP_CYCLES:
            raise ValueError(
                f"cycles must be between {-MAX_DEBUG_STEP_CYCLES} and "
                f"{MAX_DEBUG_STEP_CYCLES}, excluding 0"
            )
        if cycles < 0:
            return self.rewind(-cycles)
        return self.advance(max_cycles=cycles, capture_trace=False)

    def run(
        self,
        max_cycles=1_000,
        capture_trace=False,
        breakpoint_lines=None,
        breakpoint_robot_id=0,
    ):
        # Central validation keeps this endpoint aligned with /api/run,
        # including boolean/type checks and the stricter trace budget.
        return self.advance(
            max_cycles=max_cycles,
            capture_trace=capture_trace,
            breakpoint_lines=breakpoint_lines,
            breakpoint_robot_id=breakpoint_robot_id,
        )


class DebugSessionManager:
    """Thread-safe, TTL-bounded in-memory debugger session registry."""

    def __init__(
        self,
        max_sessions=MAX_DEBUG_SESSIONS,
        ttl_seconds=DEBUG_SESSION_TTL_SECONDS,
        clock=None,
        token_factory=None,
    ):
        if not isinstance(max_sessions, int) or isinstance(max_sessions, bool) \
                or max_sessions < 1:
            raise ValueError("max_sessions must be a positive integer")
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float)) \
                or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self._clock = clock or time.monotonic
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(18))
        self._sessions = OrderedDict()
        self._lock = threading.RLock()

    def _cleanup_locked(self, now):
        expired = [
            session_id
            for session_id, (_, last_access) in self._sessions.items()
            if now - last_access >= self.ttl_seconds
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)

    def create(self, *args, **kwargs):
        """Create and register a DebugSession, evicting least-recently-used state."""
        session = DebugSession(*args, **kwargs)
        with self._lock:
            now = self._clock()
            self._cleanup_locked(now)
            while len(self._sessions) >= self.max_sessions:
                self._sessions.popitem(last=False)

            session_id = self._token_factory()
            while session_id in self._sessions:
                session_id = self._token_factory()
            self._sessions[session_id] = (session, now)
            return session_id, session

    def get(self, session_id):
        if not isinstance(session_id, str) or not session_id:
            raise DebugSessionNotFound("Debugger session not found")
        with self._lock:
            now = self._clock()
            self._cleanup_locked(now)
            record = self._sessions.pop(session_id, None)
            if record is None:
                raise DebugSessionNotFound("Debugger session not found or expired")
            session, _ = record
            self._sessions[session_id] = (session, now)
            return session

    def delete(self, session_id):
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def active_count(self):
        with self._lock:
            now = self._clock()
            self._cleanup_locked(now)
            return len(self._sessions)
