"""
A lightweight fake of a psycopg2 connection/cursor for unit-testing the raw-SQL
utility functions in utils/room_assignment.py.

The fake records every executed query and its params, and returns rows that
the test configures via FakeConnection.queue_result_set(). Each execute() pops
one "result set" (a list of row tuples). fetchone() returns the first row of
that set; fetchall() returns the whole list. This mirrors psycopg2 semantics.
"""
from typing import List, Tuple, Any, Optional


class FakeCursor:
    """A minimal context-managed cursor stub."""

    def __init__(self, conn: "FakeConnection"):
        self.conn = conn
        self.last_query: Optional[str] = None
        self.last_params: Optional[Tuple] = None
        self._rows: List[Tuple] = []
        self._fetched: int = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query: str, params: Optional[Tuple] = None):
        self.last_query = query
        self.last_params = tuple(params) if params else ()
        self.conn.executed.append((query, self.last_params))
        # Pop the next queued result set (a list of row tuples). Default to [].
        self._rows = self.conn.result_sets.pop(0) if self.conn.result_sets else []
        self._fetched = 0

    def fetchone(self) -> Optional[Tuple]:
        if self._fetched < len(self._rows):
            row = self._rows[self._fetched]
            self._fetched += 1
            return row
        return None

    def fetchall(self) -> List[Tuple]:
        remaining = self._rows[self._fetched:]
        self._fetched = len(self._rows)
        return remaining

    def close(self):
        pass


class FakeConnection:
    """Records executed queries and serves queued result sets FIFO."""

    def __init__(self):
        # Each execute() pops one list-of-tuples from result_sets.
        self.result_sets: List[List[Tuple]] = []
        self.executed: List[Tuple[str, Tuple]] = []

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def queue_result_set(self, rows: List[Tuple]):
        """Queue a result set (list of row tuples) for the next execute()."""
        self.result_sets.append(list(rows))

    def queue_results(self, rows: List[Tuple]):
        """Back-compat alias: queue each tuple as its own single-row result set."""
        for row in rows:
            self.result_sets.append([row])

    def reset(self):
        self.result_sets.clear()
        self.executed.clear()


class FakeRoomRow:
    """Convenience row factory mimicking the tuple returned by the rooms query."""
    @staticmethod
    def make(room_id: int, code: str, name: str, max_capacity: int) -> Tuple:
        return (room_id, code, name, max_capacity)