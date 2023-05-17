<div align="center">

# nonebot-plugin-msgbuf

_✨ 适用于 NoneBot2 插件的被动消息构造集成 ✨_

~~代码比 [SAA](https://github.com/felinae98/nonebot-plugin-send-anything-anywhere) 和 [SegBuilder](https://github.com/Well2333/nonebot-plugin-segbuilder) 好看（不是）~~

<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/NCBM/nonebot-plugin-msgbuf.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-msgbuf">
  <img alt="PyPI - Downloads" src="https://img.shields.io/pypi/dm/nonebot-plugin-msgbuf">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-msgbuf">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-msgbuf.svg" alt="pypi">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-msgbuf">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-msgbuf.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="python">

</div>

## 介绍

`nonebot-plugin-msgbuf` 是帮助**开发者**快速构造与发送跨平台消息结构的应用的工具。相较于 [SAA](https://github.com/felinae98/nonebot-plugin-send-anything-anywhere) 与 [SegBuilder](https://github.com/Well2333/nonebot-plugin-segbuilder)，本插件在开发中结构更为清晰优雅。

## 适配器支持状态

| 符号 |               含义               |
| :--: | :------------------------------: |
|  ✅  |             完全支持             |
|  🟨  | 部分支持，需要用户额外分平台处理 |
|  ❌  | 不支持，发送时自动转化为后备文本 |

|                             适配器                             | 纯文本 | 图片 | 提及(@) | 回复 | 表情 | 语音 | 视频 | 文件 | 分享 | 地理位置 |
| :------------------------------------------------------------: | :----: | :--: | :-----: | :--: | :--: | :--: | :--: | :--: | :--: | :------: |
|                           OneBot V11                           |   ✅   |  ✅  |   🟨   |  🟨  |  🟨  |  ✅  |  ✅  |  ❌  |  ✅  |    ✅    |
| OneBot V11 ([Go-CQHTTP](https://github.com/Mrs4s/go-cqhttp) 拓展) |   ✅   |  ✅  |   🟨   |  🟨  |  🟨  |  ✅  |  ✅  |  ✅  |  ✅  |    ✅    |
|                           OneBot V12                           |   ✅   |  ✅  |   🟨   |  🟨  |  ❌  |  ✅  |  ✅  |  ✅  |  ❌  |    ✅    |
|                            未写明的                            |   ✅   |  ❌  |   ❌   |  ❌  |  ❌  |  ❌  |  ❌  |  ❌  |  ❌  |    ❌    |

## 安装

通过 `nb-cli`:

```console
nb plugin install nonebot-plugin-msgbuf
```

## 使用

> 关于 `require()` 的使用问题：
>
> NoneBot2 插件的**首次**导入**必须**通过 NoneBot2 自身的方式（包括但不限于 `require()`, `load_plugin()` 等）完成，否则之后使用 NoneBot2 方式导入该插件的插件将**无法**正常工作。
>
> NoneBot2 插件体系要求**必须**使用 `require()` 加载插件依赖。

### 竞品对比

这是常规的消息构造与发送方法：

<details>
<summary>展开</summary>

```python
from nonebot import on_message
from nonebot.adapters.onebot.v11 import MessageSegment
from pathlib import Path

ma = on_message()

@ma.handle()
async def test():
    await ma.send(MessageSegment.image(Path("image.png")) + "Hello world!")
```

</details>

---

这是 [SAA](https://github.com/felinae98/nonebot-plugin-send-anything-anywhere) 的消息构造与发送方法：

<details>
<summary>展开</summary>

```python
from nonebot import on_message, require
from pathlib import Path

require("nonebot_plugin_saa")

from nonebot_plugin_saa import MessageFactory, Text, Image

ma = on_message()

@ma.handle()
async def test():
    await MessageFactory([Image(Path("image.png")), Text("Hello world!")]).send()
```

</details>

---

这是 [SegBuilder](https://github.com/Well2333/nonebot-plugin-segbuilder) 的消息构造与发送方法：

<details>
<summary>展开</summary>

```python
from nonebot import on_message, require
from pathlib import Path

require("nonebot_plugin_segbuilder")

from nonebot_plugin_segbuilder import SegmentBuilder

ma = on_message()

@ma.handle()
async def test():
    await ma.send(SegmentBuilder.image(Path("image.png")) + "Hello world!")
```

</details>

---

这是 MsgBuf 的消息构造与发送方法：

```python
from nonebot import on_message, require
from pathlib import Path

require("nonebot_plugin_msgbuf")

from nonebot_plugin_msgbuf import MsgBuf

ma = on_message()

@ma.handle()
async def test():
    async with MsgBuf() as mb:
        mb.image(Path("image.png"))
        mb.text("Hello world!")
```

```python
@ma.handle()
async def test():
    async with MsgBuf() as mb:
        mb.image(Path("image.png")).text("Hello world!")
```

```python
from nonebot_plugin_msgbuf import Image, Text

@ma.handle()
async def test():
    async with MsgBuf() as mb:
        mb << Image(Path("image.png")) << Text("Hello world!")
```

```python
@ma.handle()
async def test():
    await MsgBuf().image(Path("image.png")).text("Hello world!").send()
```

### 使用 Go-CQHTTP 拓展

```python
from nonebot_plugin_msgbuf import Specs
from pathlib import Path

@ma.handle()
async def test():
    async with MsgBuf(specs=Specs.OB11_GOCQHTTP) as mb:
        mb.image(Path("image.png")).text("Hello world!").file(Path("image.png"))
```
