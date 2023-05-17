from functools import partial
from time import time
from typing import Any, Awaitable, Callable, Dict, Generic, List, Tuple, TypeVar
from typing_extensions import ParamSpec

_V = TypeVar("_V")
_P = ParamSpec("_P")


class AsyncFishCache(Generic[_P, _V]):
    def __init__(self, func: Callable[_P, Awaitable[_V]], onshelf: float = 86400.) -> None:
        self.real: List[Tuple[Tuple[Any, ...], Dict[str, Any], float, _V]] = []
        self.func = func
        self.onshelf = onshelf

    async def __call__(self, *args: _P.args, **kwds: _P.kwargs) -> _V:
        now = time()
        self.real = [t for t in self.real if now - t[2] <= self.onshelf]
        for pa, ka, _, val in self.real:
            if pa == args and ka == kwds:
                return val
        val = await self.func(*args, **kwds)
        self.real.append((args, kwds, now, val))
        return val


def async_fish_cache(onshelf: float = 86400.):
    return partial(AsyncFishCache, onshelf=onshelf)