from contextlib import suppress
from typing import Any, Generic, List, NoReturn, Type, TypeVar, overload
from nonebot import logger

from nonebot.adapters import Bot, Event

from .models import (
    Face, File, Image, Location, Mention, Model, Mutex, Raw,
    Reply, Share, Text, Video, Voice
)

_BotT = TypeVar("_BotT", bound=Bot)
_EventT = TypeVar("_EventT", bound=Event)


class Specifications:
    PLATFORM_QQ = 1
    OB11_GOCQHTTP = 1024

    def __new__(cls) -> NoReturn:
        raise NotImplementedError  # refuse creating instance


SPECS = Specs = Specifications


class BaseProxy(Generic[_BotT, _EventT]):
    bot: _BotT
    event: _EventT
    specs: int

    prefix: str = ""

    def __init__(
        self, bot: _BotT, event: _EventT, *args,
        specs: int = 0, **kwargs
    ) -> None:
        self.bot = bot
        self.event = event
        self.specs = specs

    def convert(self, seg: Model) -> str:
        return seg.alternative()
    
    async def send(
        self, *segs: Model, use_fallback: bool = False
    ) -> List[Any]:
        return [
            await self.bot.send(
                self.event, "".join(self.convert(seg) for seg in segs)
            )
        ]


registered_proxies: List[Type[BaseProxy]] = []
_ProxyT = TypeVar("_ProxyT", bound=Type[BaseProxy])


def register_proxy(proxy: _ProxyT) -> _ProxyT:
    registered_proxies.append(proxy)
    return proxy


with suppress(ImportError):
    from nonebot.adapters.onebot.v11 import (
        Bot as OB11Bot,
        Event as OB11Event,
        Message as OB11Message,
        MessageSegment as OB11MS
    )

    @register_proxy
    class OB11Proxy(BaseProxy[OB11Bot, OB11Event]):
        prefix = "nonebot.adapters.onebot.v11"

        def convert(self, seg: Model) -> OB11MS:
            if isinstance(seg, Text):
                return OB11MS.text(seg.text)
            elif isinstance(seg, Image):
                return OB11MS.image(seg.image)
            elif isinstance(seg, Mention):
                return OB11MS.at(
                    int(seg.user_id) if seg.user_id.isdigit() else seg.user_id
                )
            elif isinstance(seg, Reply):
                return OB11MS.reply(int(seg.msg_id))
            elif isinstance(seg, Face):
                return OB11MS.face(int(seg.face_id))
            elif isinstance(seg, Voice):
                return OB11MS.record(seg.voice)
            elif isinstance(seg, Video):
                return OB11MS.video(seg.video)
            elif isinstance(seg, Share):
                return OB11MS.share(
                    seg.url, seg.title, seg.content or None, seg.image or None
                )
            elif isinstance(seg, Location):
                return OB11MS.location(
                    seg.lat, seg.lon, seg.title or None, seg.content or None
                )
            else:
                return OB11MS.text(seg.alternative())
        
        async def send(self, *segs: Model, use_fallback: bool = False) -> List[Any]:
            if use_fallback:
                return await super().send(*segs)
            call_result = []
            msg = OB11Message()
            for seg in segs:
                if isinstance(seg, Mutex):
                    if msg:
                        logger.info(
                            f"{seg.__class__.__name__} 类型与 Body 类型冲突，"
                            "无法在一条内发送！"
                        )
                        call_result.append(
                            await self.bot.send(self.event, msg)
                        )
                        msg.clear()
                    if (
                        (self.specs & SPECS.OB11_GOCQHTTP)
                        and isinstance(seg, File)
                    ):
                        send_file = self.bot.upload_private_file
                        idarg = {"user_id": getattr(self.event, "user_id")}
                        if (
                            tid := getattr(self.event, "group_id", None)
                        ) is not None:
                            send_file = self.bot.upload_group_file
                            idarg = {"group_id": tid}
                        call_result.append(
                            await send_file(
                                **idarg,
                                file=seg.local_path(), name=seg.name
                            )
                        )
                    elif isinstance(seg, Raw) and isinstance(
                        seg.raw, (str, OB11MS, OB11Message)
                    ):
                        call_result.append(
                            await self.bot.send(self.event, seg.raw)
                        )
                    else:
                        call_result.append(
                            await self.bot.send(self.event, self.convert(seg))
                        )
                else:
                    if msg["reply"] and isinstance(seg, Image):
                        logger.warning("Image 类型与 Reply 类型冲突，无法在一条内发送！")
                        call_result.append(
                            await self.bot.send(self.event, msg)
                        )
                        msg.clear()
                    msg.append(self.convert(seg))
            if msg:
                call_result.append(await self.bot.send(self.event, msg))
            return call_result


    @overload
    def find_proxy(bot: OB11Bot) -> Type[OB11Proxy]:
        ...


@overload
def find_proxy(bot: Bot) -> Type[BaseProxy]:
    ...


def find_proxy(bot: Bot) -> Type[BaseProxy]:
    for p in registered_proxies:
        if bot.__module__.startswith(p.prefix):
            return p
    return BaseProxy