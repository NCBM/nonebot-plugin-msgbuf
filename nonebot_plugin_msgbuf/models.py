from dataclasses import dataclass
from io import BytesIO
from os.path import basename
from pathlib import Path
from typing import Literal, Union

from nonebot.adapters import Message, MessageSegment

SupportedFileData = Union[str, Path, bytes, BytesIO]

# -*- stub definitions -*-


class Model:
    """用于描述消息单体类型关系的记号类型。"""
    _model_basetype: Literal["Body", "Mutex", "Single"]
    _model_single: bool = False

    def alternative(self) -> str:
        return "[不支持的消息类型]"


class Body(Model):
    """用于描述正文消息单体类型关系的记号类型。"""
    _model_basetype = "Body"


class Mutex(Model):
    """用于描述互斥消息单体类型关系的记号类型。"""
    _model_basetype = "Mutex"


class Single(Body):
    """用于描述限量正文消息单体类型关系的记号类型。"""
    _model_single = True


# -*- end stub definitions -*-
# -*- common models definitions -*-


@dataclass
class Raw(Mutex):
    raw: Union[str, Message, MessageSegment]


@dataclass
class Text(Body):
    text: str

    def alternative(self) -> str:
        return self.text


@dataclass
class Image(Body):
    image: SupportedFileData

    def alternative(self) -> str:
        return "[图片]"


@dataclass
class Mention(Body):
    user_id: str

    def alternative(self) -> str:
        return f"@{self.user_id} "


@dataclass
class Reply(Single):
    msg_id: str

    def alternative(self) -> str:
        return "[回复]"


# -*- end common models definitions -*-
# -*- platform specific models definitions -*-


@dataclass
class Face(Body):
    face_id: str

    def alternative(self) -> str:
        return "[表情]"


@dataclass
class Voice(Mutex):
    voice: SupportedFileData

    def alternative(self) -> str:
        return "[语音]"


@dataclass
class Video(Mutex):
    video: SupportedFileData

    def alternative(self) -> str:
        return "[视频]"


@dataclass
class File(Mutex):
    file: SupportedFileData
    name: str = ""

    def __post_init__(self) -> None:
        if self.name:
            return
        elif isinstance(self.file, (bytes, BytesIO)):
            raise ValueError("Cannot get file name")
        elif isinstance(self.file, Path):
            self.name = Path(self.file).name
        elif self.file.startswith("base"):
            raise
        else:
            end = basename(self.file)
            if self.file.startswith("http"):
                pa = end.find('?')
                end = end[:pa] if pa > 0 else end
            self.name = end

    def local_path(self) -> str:
        if isinstance(self.file, (bytes, BytesIO)):
            raise ValueError("Cannot get file path")
        elif isinstance(self.file, Path):
            return str(self.file)
        elif self.file.startswith("file://"):
            return self.file[7:]
        raise ValueError("File is not local file")

    def alternative(self) -> str:
        return "[文件]"


@dataclass
class Share(Mutex):
    url: str
    title: str
    content: str = ""
    image: str = ""

    def alternative(self) -> str:
        return f"[分享] 《{self.title}》 {self.url}"


@dataclass
class Location(Mutex):
    lat: float
    lon: float
    title: str = ""
    content: str = ""

    def alternative(self) -> str:
        return f"[纬度：{self.lat}，经度：{self.lon}]"


# -*- end platform specific models definitions -*-