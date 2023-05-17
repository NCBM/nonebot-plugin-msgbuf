import asyncio
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from typing import Any, Generic, List, NoReturn, Type, TypeVar, overload
from nonebot import logger

from nonebot.adapters import Bot, Event

from .utils import async_fish_cache

from .models import (
    Face, File, Image, Location, Mention, Model, Mutex, Raw,
    Reply, Share, SupportedFileData, Text, Video, Voice
)

_BotT = TypeVar("_BotT", bound=Bot)
_EventT = TypeVar("_EventT", bound=Event)


class Specifications:
    PLATFORM_QQ = 1
    OB11_GOCQHTTP = 1024 + PLATFORM_QQ

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

    async def convert(self, seg: Model) -> str:
        return seg.alternative()
    
    async def send(
        self, *segs: Model, use_fallback: bool = False
    ) -> List[Any]:
        return [
            await self.bot.send(
                self.event, "".join(
                    await asyncio.gather(*(self.convert(seg) for seg in segs))
                )
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

        async def convert(self, seg: Model) -> OB11MS:
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
                            await self.bot.send(self.event, await self.convert(seg))
                        )
                else:
                    if (self.specs & SPECS.PLATFORM_QQ) and msg["reply"] and isinstance(seg, Image):
                        logger.warning("Image 类型与 Reply 类型冲突，无法在一条内发送！")
                        call_result.append(
                            await self.bot.send(self.event, msg)
                        )
                        msg.clear()
                    msg.append(await self.convert(seg))
            if msg:
                call_result.append(await self.bot.send(self.event, msg))
            return call_result


    @overload
    def find_proxy(bot: OB11Bot) -> Type[OB11Proxy]:
        ...


with suppress(ImportError):
    from nonebot.adapters.onebot.v12 import (
        Bot as OB12Bot,
        Event as OB12Event,
        Message as OB12Message,
        MessageSegment as OB12MS
    )

    @async_fish_cache()
    async def _ob12_upload_file(bot: OB12Bot, file: SupportedFileData, name: str) -> str:
        if isinstance(file, str):
            if "://" in file:
                res = await bot.upload_file(type="url", name=name, url=file)
            else:
                res = await bot.upload_file(type="path", name=name, path=file)
        elif isinstance(file, Path):
            res = await bot.upload_file(type="path", name=name, path=str(file))
        elif isinstance(file, bytes):
            res = await bot.upload_file(type="bytes", name=name, data=file)
        elif isinstance(file, BytesIO):
            res = await bot.upload_file(type="bytes", name=name, data=file.getvalue())
        else:
            raise ValueError("不受支持的数据形式")
        logger.info(f"成功上传文件 {name!r}")
        return res["file_id"]

    @register_proxy
    class OB12Proxy(BaseProxy[OB12Bot, OB12Event]):
        prefix = "nonebot.adapters.onebot.v12"

        async def upload_file(self, file: SupportedFileData, name: str) -> str:
            return await _ob12_upload_file(self.bot, file, name)

        async def convert(self, seg: Model) -> OB12MS:
            if isinstance(seg, Text):
                return OB12MS.text(seg.text)
            elif isinstance(seg, Mention):
                return OB12MS.mention(seg.user_id)
            elif isinstance(seg, Reply):
                return OB12MS.reply(seg.msg_id)
            elif isinstance(seg, Image):
                return OB12MS.image(await self.upload_file(seg.image, seg.name))
            elif isinstance(seg, Voice):
                return OB12MS.voice(await self.upload_file(seg.voice, seg.name))
            elif isinstance(seg, Video):
                return OB12MS.video(await self.upload_file(seg.video, seg.name))
            elif isinstance(seg, File):
                return OB12MS.file(await self.upload_file(seg.file, seg.name))
            elif isinstance(seg, Location):
                return OB12MS.location(
                    seg.lat, seg.lon, seg.title, seg.content
                )
            else:
                return OB12MS.text(seg.alternative())
            
        async def send(self, *segs: Model, use_fallback: bool = False) -> List[Any]:
            if use_fallback:
                return await super().send(*segs)
            call_result = []
            msg = OB12Message()
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
                    if isinstance(seg, Raw) and isinstance(
                        seg.raw, (str, OB12MS, OB12Message)
                    ):
                        call_result.append(
                            await self.bot.send(self.event, seg.raw)
                        )
                    else:
                        call_result.append(
                            await self.bot.send(self.event, await self.convert(seg))
                        )
                else:
                    if (self.specs & SPECS.PLATFORM_QQ) and msg["reply"] and isinstance(seg, Image):
                        logger.warning("Image 类型与 Reply 类型冲突，无法在一条内发送！")
                        call_result.append(
                            await self.bot.send(self.event, msg)
                        )
                        msg.clear()
                    msg.append(await self.convert(seg))
            if msg:
                call_result.append(await self.bot.send(self.event, msg))
            return call_result


@overload
def find_proxy(bot: Bot) -> Type[BaseProxy]:
    ...


def find_proxy(bot: Bot) -> Type[BaseProxy]:
    for p in registered_proxies:
        if bot.__module__.startswith(p.prefix):
            return p
    return BaseProxy