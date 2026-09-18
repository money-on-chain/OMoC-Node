"""Exact per-market risk heaps. Access is serialized by LendingRepository."""
import heapq
from dataclasses import dataclass


@dataclass(frozen=True)
class RiskVault:
    user: str
    tp_token: str
    moc_bucket: str
    ac_balance: str
    credit_units: str
    liquidating: bool
    generation: int

    @classmethod
    def from_state(cls, state):
        return cls(**{name: state[name] for name in cls.__dataclass_fields__})


class Entry:
    def __init__(self, vault):
        self.vault = vault
        self.ac = int(vault.ac_balance)
        self.credit = int(vault.credit_units)

    def __lt__(self, other):
        if self.vault.liquidating != other.vault.liquidating:
            return self.vault.liquidating
        if (self.ac == 0) != (other.ac == 0):
            return self.ac == 0
        if self.ac and other.ac:
            left, right = self.credit * other.ac, other.credit * self.ac
            if left != right:
                return left > right
        return self.vault.user < other.vault.user


class RiskIndex:
    def __init__(self):
        self.markets = {}

    def update(self, state):
        vault = RiskVault.from_state(state)
        key = (vault.tp_token, vault.moc_bucket)
        heap, current = self.markets.setdefault(key, ([], {}))
        if int(vault.credit_units) == 0 and not vault.liquidating:
            current.pop(vault.user, None)
        else:
            entry = Entry(vault)
            current[vault.user] = entry
            heapq.heappush(heap, entry)
        # Identity invalidates stale generations even after rollback/replay.
        if len(heap) > max(64, 2 * len(current)):
            heap[:] = current.values()
            heapq.heapify(heap)
        if not current:
            self.markets.pop(key, None)

    def top(self, tp_token, moc_bucket, limit):
        heap, current = self.markets.get((tp_token.lower(), moc_bucket.lower()), ([], {}))
        selected = []
        while heap and len(selected) < max(0, limit):
            entry = heapq.heappop(heap)
            if current.get(entry.vault.user) is entry:
                selected.append(entry)
        for entry in selected:
            heapq.heappush(heap, entry)
        return [entry.vault for entry in selected]

    def count(self):
        return sum(len(current) for _, current in self.markets.values())
