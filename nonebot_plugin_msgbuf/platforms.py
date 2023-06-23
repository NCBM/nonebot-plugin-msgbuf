import asyncio
from collections import deque
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from types import TracebackType
from typing import Any, Deque, Generic, List, Literal, NoReturn, Optional, Tuple, Type, TypeVar, Union, cast, overload
from nonebot import logger

from nonebot.adapters import Bot, Event
from nonebot.exception import ActionFailed

from .base import MsgBufManager
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

    registered_proxies: List[Type["BaseProxy"]] = []

    def __init__(
        self, bot: _BotT, event: _EventT, *args,
        specs: int = 0, **kwargs
    ) -> None:
        self.bot = bot
        self.event = event
        self.specs = specs

    def __init_subclass__(cls) -> None:
        BaseProxy.registered_proxies.append(cls)

    async def convert(self, seg: Model) -> str:
        return seg.alternative()
    
    async def flush_with_log(self, msg, cres, log: str, log_level: str = "info"):
        if msg:
            logger.log(log_level, log)
            cres.append(await self.bot.send(self.event, msg))
            msg.clear()
    
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


_ProxyT = TypeVar("_ProxyT", bound=Type[BaseProxy])


with suppress(ImportError):
    from nonebot.adapters.onebot.v11 import (
        Bot as OB11Bot,
        Event as OB11Event,
        Message as OB11Message,
        MessageSegment as OB11MS,
        MessageEvent as OB11MsgEv
    )

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
            elif isinstance(seg, Raw) and seg.raw.__module__.startswith(self.prefix):
                return cast(OB11MS, seg.raw)
            return OB11MS.text(seg.alternative())
        
        async def send(self, *segs: Model, use_fallback: bool = False) -> List[Any]:
            if use_fallback:
                return await super().send(*segs)
            call_result = []
            msg = OB11Message()
            for seg in segs:
                if isinstance(seg, Mutex):
                    await self.flush_with_log(
                        msg, call_result,
                        f"{seg.__class__.__name__} 类型与 Body 类型冲突，无法在一条内发送！"
                    )
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
                        await self.flush_with_log(msg, call_result, "Image 类型与 Reply 类型冲突，无法在一条内发送！")
                    msg.append(await self.convert(seg))
            if msg:
                call_result.append(await self.bot.send(self.event, msg))
            return call_result

    @overload
    def find_proxy(bot: OB11Bot) -> Type[OB11Proxy]:
        ...

    class ForwardNode(MsgBufManager):
        """转发消息节点构造器"""

        def __init__(
            self, fb: "ForwardBuffer", uid: int, name: str,
            fn: Optional["ForwardNode"] = None, allow_incomplete: bool = False
        ) -> None:
            self.fb, self.fn = fb, fn
            self.uid, self.name = uid, name
            self.allow_incomplete = allow_incomplete
            super().__init__()

        async def __aenter__(self):
            return self
        
        async def __aexit__(
            self,
            exc_tp: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[TracebackType]
        ) -> Optional[bool]:
            if exc_tb and not self.allow_incomplete:
                return False
            if self.fn is not None:
                self.fn.msgbuf.append(
                    Raw(
                        OB11MS(
                            "node",
                            {"uin": self.uid, "name": self.name, "content": await self.export()}
                        )
                    )
                )
            else:
                self.fb.fwdbuf.append(
                    OB11MS(
                        "node",
                        {"uin": self.uid, "name": self.name, "content": await self.export()}
                    )
                )
            
        def node(self, uid: int, name: str) -> "ForwardNode":
            """
            创建消息节点

            - uid: （显示的）节点发送者 QQ 号（决定发送者头像）
            - name: （显示的）昵称
            """
            return ForwardNode(self.fb, uid, name, self, allow_incomplete=self.allow_incomplete)

        async def export(self) -> List[OB11MS]:
            return await asyncio.gather(
                *(self.fb.proxy.convert(s) for s in self.msgbuf)
            )

    class ForwardBuffer:
        """转发消息构造器"""

        def __init__(
            self,
            bot: OB11Bot,
            dest: Tuple[Literal["private", "group"], int],
            *,
            send: bool = True, send_incomplete: bool = False,
            retry: int = 0, cooldown: float = 5.
        ) -> None:
            """
            初始化转发消息构造器

            - bot: 机器人对象
            - dest: 发送目标
            - send: 是否进行发送
            - send_incomplete: 是否在上下文内部出错后仍发送
            - retry: 重试次数
            - cooldown: 重试冷却
            """
            self.bot = bot
            self.dest = dest
            self.proxy = find_proxy(bot)(bot, None)  # type: ignore
            self.fwdbuf: Deque[OB11MS] = deque()
            self.ifsend = send
            self.send_incomplete = send_incomplete
            self.retry = retry
            self.cooldown = cooldown

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_tp: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[TracebackType]
        ) -> Optional[bool]:
            if (
                self.ifsend                                 # send switch
                and (not exc_tb or self.send_incomplete)    # noerror or inc.
                and self.fwdbuf                             # not empty
            ):
                await self.send()
            if exc_tb:
                return False
            
        def node(self, uid: int, name: str) -> ForwardNode:
            """
            创建消息节点

            - uid: （显示的）节点发送者 QQ 号（决定发送者头像）
            - name: （显示的）昵称
            """
            return ForwardNode(self, uid, name, allow_incomplete=self.send_incomplete)

        @overload
        async def get_sender_name(
            self, *,
            uid: int,
            gid: Optional[int] = None,
            cache: bool = True
        ) -> str:
            ...

        @overload
        async def get_sender_name(
            self, *,
            event: OB11Event,
            cache: bool = True
        ) -> str:
            ...

        async def get_sender_name(
            self, *,
            uid: Optional[int] = None,
            gid: Optional[int] = None,
            event: Optional[OB11Event] = None,
            cache: bool = True
        ) -> str:
            """获取用户名称"""
            if event and cache:
                uid = getattr(event, "user_id", event.self_id)
                if isinstance(event, OB11MsgEv):
                    return event.sender.card or event.sender.nickname or str(uid)
                gid = getattr(event, "group_id", None)
            if uid is None:
                raise ValueError("无有效用户 ID")
            elif gid is not None:
                info = await self.bot.get_group_member_info(
                    group_id=gid, user_id=uid, no_cache=not cache
                )
                return str(info["card"] or info["nickname"])
            else:
                return (await self.bot.get_stranger_info(user_id=uid, no_cache=not cache))["nickname"]

        async def send(self) -> Any:
            """发送消息"""
            dtype, did = self.dest
            if dtype == "group":
                sender = self.bot.send_group_forward_msg
                kwds = {"group_id": did, "messages": self.fwdbuf}
            else:
                sender = self.bot.send_private_forward_msg
                kwds = {"user_id": did, "messages": self.fwdbuf}

            try:
                res = await sender(**kwds)
                logger.success("消息发送成功！")
                return res
            except ActionFailed:
                if self.retry > 0:
                    logger.warning(f"消息发送失败，剩余 {self.retry} 次重试。")
                    await asyncio.sleep(self.cooldown)
                    self.retry -= 1
                    return await self.send()
                logger.error("消息发送失败！")
                raise


with suppress(ImportError):
    from nonebot.adapters.onebot.v12 import (
        Bot as OB12Bot,
        Event as OB12Event,
        Message as OB12Message,
        MessageSegment as OB12MS
    )

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

    class OB12Proxy(BaseProxy[OB12Bot, OB12Event]):
        prefix = "nonebot.adapters.onebot.v12"

        async def upload_file(self, file: SupportedFileData, name: str) -> str:
            return await _ob12_upload_file(self.bot, file, name)

        async def convert(self, seg: Model) -> OB12MS:
            if isinstance(seg, Text):
                return OB12MS.text(seg.text)
            elif isinstance(seg, Mention):
                return OB12MS.mention(seg.user_id) if seg.user_id != "@all" else OB12MS.mention_all()
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
            elif isinstance(seg, Raw) and seg.raw.__module__.startswith(self.prefix):
                return cast(OB12MS, seg.raw)
            return OB12MS.text(seg.alternative())
            
        async def send(self, *segs: Model, use_fallback: bool = False) -> List[Any]:
            if use_fallback:
                return await super().send(*segs)
            call_result = []
            msg = OB12Message()
            for seg in segs:
                if isinstance(seg, Mutex):
                    await self.flush_with_log(msg, call_result, f"{seg.__class__.__name__} 类型与 Body 类型冲突，无法在一条内发送！")
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
                        await self.flush_with_log(msg, call_result, "Image 类型与 Reply 类型冲突，无法在一条内发送！")
                    msg.append(await self.convert(seg))
            if msg:
                call_result.append(await self.bot.send(self.event, msg))
            return call_result

    @overload
    def find_proxy(bot: OB12Bot) -> Type[OB12Proxy]:
        ...


with suppress(ImportError):
    from nonebot.adapters.qqguild import (
        Bot as QGBot,
        Event as QGEvent,
        Message as QGMessage,
        MessageSegment as QGMS
    )

    class QGProxy(BaseProxy[QGBot, QGEvent]):
        prefix = "nonebot.adapters.qqguild"

        async def convert(self, seg: Model) -> QGMS:
            if isinstance(seg, Text):
                return QGMS.text(seg.text)
            elif isinstance(seg, Image):
                return QGMS.image(seg.image) if isinstance(seg.image, str) else QGMS.file_image(seg.image)
            elif isinstance(seg, Mention):
                if seg.domain == "channel":
                    return QGMS.mention_channel(int(seg.user_id))
                return QGMS.mention_user(int(seg.user_id))
            elif isinstance(seg, Reply):
                return QGMS.reference(seg.msg_id)
            elif isinstance(seg, Face):
                return QGMS.emoji(seg.face_id)
            elif isinstance(seg, Raw) and seg.raw.__module__.startswith(self.prefix):
                return cast(QGMS, seg.raw)
            return QGMS.text(seg.alternative())

        async def send(self, *segs: Model, use_fallback: bool = False) -> List[Any]:
            if use_fallback:
                return await super().send(*segs)
            call_result = []
            msg = QGMessage()
            for seg in segs:
                if isinstance(seg, Image) and (msg["attachment"] or msg["file_image"]):
                    await self.flush_with_log(msg, call_result, "Image 类型数量受限，无法在一条内发送！")
                elif isinstance(seg, Reply) and msg["reference"]:
                    await self.flush_with_log(msg, call_result, "Reply 类型数量受限，无法在一条内发送！")
                elif isinstance(seg, Raw) and isinstance(
                    seg.raw, (str, QGMS, QGMessage)
                ):
                    await self.flush_with_log(msg, call_result, "Raw 类型无法在一条内发送！")
                    call_result.append(
                        await self.bot.send(self.event, seg.raw)
                    )
                else:
                    msg.append(await self.convert(seg))
            if msg:
                call_result.append(await self.bot.send(self.event, msg))
            return call_result

    @overload
    def find_proxy(bot: QGBot) -> Type[QGProxy]:
        ...


with suppress(ImportError):
    from nonebot.adapters.telegram import (
        Bot as TGBot,
        Event as TGEvent,
        Message as TGMessage,
        MessageSegment as TGMS
    )
    from nonebot.adapters.telegram.message import (
        Entity as TGRichTextMS,
        UnCombinFile as TGFileMS
    )

    class TGProxy(BaseProxy[TGBot, TGEvent]):
        prefix = "nonebot.adapters.telegram"

        async def convert(self, seg: Model) -> TGMS:
            if isinstance(seg, Text):
                if not seg.rich:
                    return TGRichTextMS.text(seg.text)
                elif seg.rich in (
                    "hashtag", "cashtag", "bot_command", "url", "email", "phone_number",
                    "bold", "italic", "underline", "strikethrough", "spoiler", "code", "pre"
                ):
                    return getattr(TGRichTextMS, seg.rich)(seg.text)
                logger.warning(f"未识别的富文本格式 {seg.rich!r}，将作为纯文本发送")
            elif isinstance(seg, Image):
                if isinstance(seg.image, BytesIO):
                    return TGFileMS.photo(seg.image.getvalue())
                elif isinstance(seg.image, bytes):
                    return TGFileMS.photo(seg.image)
                return TGFileMS.photo(File(seg.image, seg.name).local_path())
            elif isinstance(seg, Mention):
                if seg.tg_user is None:
                    return TGRichTextMS.mention(f"@{seg.user_id}")
                return TGRichTextMS.text_mention(seg.user_id, seg.tg_user)
            elif isinstance(seg, Face):
                return TGFileMS.sticker(seg.face_id)
            elif isinstance(seg, Voice):
                if isinstance(seg.voice, BytesIO):
                    return TGFileMS.voice(seg.voice.getvalue())
                elif isinstance(seg.voice, bytes):
                    return TGFileMS.voice(seg.voice)
                return TGFileMS.voice(File(seg.voice, seg.name).local_path())
            elif isinstance(seg, Video):
                if isinstance(seg.video, BytesIO):
                    return TGFileMS.video(seg.video.getvalue())
                elif isinstance(seg.video, bytes):
                    return TGFileMS.video(seg.video)
                return TGFileMS.video(File(seg.video, seg.name).local_path())
            elif isinstance(seg, File):
                if isinstance(seg.file, BytesIO):
                    return TGFileMS.document(seg.file.getvalue())
                elif isinstance(seg.file, bytes):
                    return TGFileMS.document(seg.file)
                return TGFileMS.document(seg.local_path())
            elif isinstance(seg, Location):
                return TGMS.location(seg.lat, seg.lon)
            elif isinstance(seg, Raw) and seg.raw.__module__.startswith(self.prefix):
                return cast(TGMS, seg.raw)
            return TGRichTextMS.text(seg.alternative())

        async def send(self, *segs: Model, use_fallback: bool = False) -> List[Any]:
            if use_fallback:
                return await super().send(*segs)
            call_result = []
            msg = TGMessage()
            reply = None
            for seg in segs:
                if isinstance(seg, Mutex):
                    await self.flush_with_log(msg, call_result, f"{seg.__class__.__name__} 类型与 Body 类型冲突，无法在一条内发送！")
                    if isinstance(seg, Raw) and isinstance(
                        seg.raw, (str, TGMS, TGMessage)
                    ):
                        call_result.append(
                            await self.bot.send(self.event, seg.raw, reply_to_message_id=reply)
                        )
                    else:
                        call_result.append(
                            await self.bot.send(self.event, await self.convert(seg), reply_to_message_id=reply)
                        )
                else:
                    if isinstance(seg, Reply):
                        reply = int(seg.msg_id)
                        continue
                    msg.append(await self.convert(seg))
            if msg:
                call_result.append(await self.bot.send(self.event, msg, reply_to_message_id=reply))
            return call_result

    @overload
    def find_proxy(bot: TGBot) -> Type[TGProxy]:
        ...


@overload
def find_proxy(bot: _BotT) -> Type[BaseProxy[_BotT, Any]]:
    ...


def find_proxy(bot: Bot) -> Type[BaseProxy]:
    return next(
        (
            p
            for p in BaseProxy.registered_proxies
            if bot.__module__.startswith(p.prefix)
        ),
        BaseProxy,
    )