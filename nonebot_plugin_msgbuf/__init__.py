import asyncio
from collections import deque
from types import TracebackType
from typing import (
    Any,        Deque,      Generic,    List,       Optional,   Type,
    Union,      cast
)
from nonebot import logger, __version__ as nbver
from nonebot.adapters import MessageSegment
from nonebot.exception import ActionFailed
from nonebot.matcher import current_bot, current_event
from nonebot.plugin import PluginMetadata

from .models import (
    Face,               File,               Image,              Location,
    Mention,            Model,              Raw,                Reply,
    Share,              SupportedFileData,  Text,               Video,
    Voice
)
from .platforms import _BotT, _EventT, Specs, find_proxy

_extra_meta_source = {
    "type": "library",
    "homepage": "https://github.com/NCBM/nonebot-plugin-msgbuf"
}

if (
    not nbver
    or not nbver.startswith("2.0.0")
    or not (_suf := nbver[5:])
    or _suf[0] not in "abr"
    or (_suf.startswith("rc") and int(_suf[2:]) > 4)
):
    _extra_meta = _extra_meta_source
else:
    _extra_meta = {"extra": _extra_meta_source}

__plugin_meta__ = PluginMetadata(
    name="信鸽巴夫",
    description="适用于 NoneBot2 插件的被动消息构造集成",
    usage="无",
    **_extra_meta
)


class MessageBuffer(Generic[_BotT, _EventT]):
    """消息构造器"""

    def __init__(
        self,
        bot: Optional[_BotT] = None,
        event: Optional[_EventT] = None,
        *,
        specs: int = 0,
        send: bool = True, send_incomplete: bool = False,
        retry: int = 0, fallback: int = 0, cooldown: float = 5.
    ) -> None:
        """
        初始化消息构造器

        - bot: 机器人对象
        - event: 响应事件
        - specs: 特殊规则
        - send: 是否进行发送（需要异步上下文）
        - send_incomplete: 是否在上下文内部出错后仍发送
        - retry: 重试次数
        - fallback: 后备（通常是纯文本）重试次数
        - cooldown: 重试冷却
        """
        if bot is None:
            bot = cast(_BotT, current_bot.get())
        if event is None:
            event = cast(_EventT, current_event.get())
        self.proxy = find_proxy(bot)(bot, event, specs=specs)
        self.msgbuf: Deque[Model] = deque()
        self.ifsend = send
        self.send_incomplete = send_incomplete
        self.retry = retry
        self.fallback = fallback
        self.cooldown = cooldown

    def __enter__(self):
        return self

    async def __aenter__(self):
        return self

    def __exit__(
        self,
        exc_tp: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> Optional[bool]:
        if exc_tb and not self.send_incomplete:
            return False
        if self.ifsend:
            logger.warning("未使用异步上下文，无法发送消息！")
        if exc_tb:
            return False
    
    async def __aexit__(
        self,
        exc_tp: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> Optional[bool]:
        if (
            self.ifsend                                 # send switch
            and (not exc_tb or self.send_incomplete)    # noerror or inc.
            and self.msgbuf                             # not empty
        ):
            await self.send()
        if exc_tb:
            return False

    def __lshift__(self, __o: Model):
        self.msgbuf.append(__o)
        return self

    def add(self, *m: Model):
        """批量插入消息结构"""
        self.msgbuf.extend(m)
        return self
    
    async def export(
        self, convert: bool = False
    ) -> Union[List[MessageSegment], List[Model], List[str]]:
        if convert:
            return await asyncio.gather(
                *(self.proxy.convert(s) for s in self.msgbuf)
            )
        return list(self.msgbuf)

    def revert(self, n: int = 1):
        """
        从末尾删除消息结构
        
        - n: 删除个数
        """
        for _ in range(n):
            self.msgbuf.pop()
        return self

    async def send(self, *, use_fallback: bool = False) -> List[Any]:
        """
        发送消息

        - use_fallback: 是否使用后备
        """
        try:
            res = await self.proxy.send(
                *self.msgbuf, use_fallback=use_fallback
            )
            logger.success("消息发送成功！")
            return res
        except ActionFailed:
            if self.retry > 0:
                logger.warning(f"消息发送失败，剩余 {self.retry} 次重试。")
                await asyncio.sleep(self.cooldown)
                self.retry -= 1
                return await self.send()
            elif self.fallback > 0:
                logger.warning(f"消息发送失败，剩余 {self.fallback} 次重试（后备）。")
                await asyncio.sleep(self.cooldown)
                self.fallback -= 1
                return await self.send(use_fallback=True)
            logger.error("消息发送失败！")
            raise
    
    async def flush(self):
        """发送当前缓冲的消息并清空缓冲区"""
        res = await self.send()
        self.msgbuf.clear()
        return res

    def text(self, text: str):
        """追加普通文本"""
        self.msgbuf.append(Text(text))
        return self

    def image(self, image: SupportedFileData):
        """追加图片"""
        self.msgbuf.append(Image(image))
        return self

    def mention(self, uid: Union[str, int]):
        """追加提及 (At)"""
        self.msgbuf.append(Mention(str(uid)))
        return self

    def reply(self, mid: Union[str, int]):
        """追加回复"""
        self.msgbuf.append(Reply(str(mid)))
        return self

    def face(self, fid: Union[str, int]):
        """追加表情"""
        self.msgbuf.append(Face(str(fid)))
        return self

    def voice(self, voice: SupportedFileData):
        """追加语音"""
        self.msgbuf.append(Voice(voice))
        return self

    def video(self, video: SupportedFileData):
        """追加视频"""
        self.msgbuf.append(Video(video))
        return self

    def file(self, file: SupportedFileData, name: str = ""):
        """追加文件"""
        self.msgbuf.append(File(file, name))
        return self
    
    def share(self, url: str, title: str, content: str = "", image: str = ""):
        """追加分享"""
        self.msgbuf.append(Share(url, title, content, image))
        return self
    
    def location(
        self,
        latitude: float, lontitude: float,
        title: str = "", content: str = ""
    ):
        """追加地理位置"""
        self.msgbuf.append(Location(latitude, lontitude, title, content))
        return self


MsgBuf = MessageBuffer

__all__ = (
    "Face",     "File",     "Image",    "Location", "Mention",  "Raw",
    "Reply",    "Share",    "Text",     "Video",    "Voice",
    "MessageBuffer",        "MsgBuf",               "Specs"
)