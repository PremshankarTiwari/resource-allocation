from .base import AllocationResult, Allocator
from .greedy import GreedyAllocator
from .hungarian import HungarianAllocator
from .regret import RegretAllocator

ALLOCATORS: dict[str, Allocator] = {
    a.key: a for a in (GreedyAllocator(), HungarianAllocator(), RegretAllocator())
}

__all__ = ["ALLOCATORS", "AllocationResult", "Allocator"]
