from collections import deque
from typing import Deque, Union

from nonebot.adapters import MessageSegment
from .models import (
    Face,               File,               Image,              Location,
    Mention,            Model,              Raw,                Reply,
    Share,              SupportedFileData,  Text,               Video,
    Voice
)


class MsgBufManager:
    def __init__(self) -> None:
        self.msgbuf: Deque[Model] = deque()

    def __lshift__(self, __o: Model):
        self.msgbuf.append(__o)
        return self

    def add(self, *m: Model):
        """批量插入消息结构"""
        self.msgbuf.extend(m)
        return self

    def revert(self, n: int = 1):
        """
        从末尾删除消息结构
        
        - n: 删除个数
        """
        for _ in range(n):
            self.msgbuf.pop()
        return self
    
    def raw(self, raw: Union[str, MessageSegment]):
        """追加原始消息/消息段"""
        self.msgbuf.append(Raw(raw))
        return self

    def text(self, text: str):
        """追加普通文本"""
        self.msgbuf.append(Text(text))
        return self

    def image(self, image: SupportedFileData):
        """追加图片"""
        self.msgbuf.append(Image(image))
        return self

    def mention(self, uid: Union[str, int], domain: str = ""):
        """追加提及 (At)"""
        self.msgbuf.append(Mention(str(uid), domain))
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