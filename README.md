# ass-select-bottom-subtitles-to-lrc

【猫耳FM广播剧字幕提取】批量处理猫耳FM的xml弹幕转换成的ass弹幕，运用正则筛选出其中的底部弹幕，并转换成lrc格式字幕文件。

⚠️程序基本由AI编写，作者只负责提出需求，完善功能和测试可用，并不懂python。因此当您遇到出乎预料的使用问题时，可能无法给您提供有用的建议。

⚠️默认编码全为utf-8。

✅经作者测试可用的python版本为Python 3.11.9

## 如何使用

1. 通过我的这个油猴脚本[fishhh666/-FM-XML-: 记录猫耳FM / missevan 的 标题和网址，可导出为 JSON 方便后期处理其他任务。脚本支持下载当前页面弹幕 xml 或记录中的所有页面对应 xml（只能逐个下载）](https://github.com/fishhh666/-FM-XML-)导出需要下载弹幕网页的网址和标题，导出到link.json
2. 下载并运行同目录下的download_xml.py

   (也在上述仓库中，直达链接
[-FM-XML-/download_xml.py at main · fishhh666/-FM-XML-](https://github.com/fishhh666/-FM-XML-/blob/main/download_xml.py) ）

程序运行后的一个典型的文件结构示例如下:
```
.
├── link.json                (油猴脚本导出，程序优先识别)
├── link.txt                 (备选，一行一个手动输入网址，link.json不存在则识别该文件)
├── 🐍 download_xml.py       (程序本体，上面两个文件必须二者有一)
└── 📁 XML/                  (存放下载好的XML文件)
    ├── 1-123456.xml            (如果是读取txt下载的: 序号-猫耳音频ID)
    └── 网页标题.xml             (如果是读取json下载的: 网页标题)

```

4. 通过 [弹幕盒子 - 转换](https://danmubox.github.io/convert) 批量将xml转换成ass.⭐到这步就可以在potplayer中看到全滚动弹幕和底部字幕。

⚠️⚠️⚠️ **由于本程序（process_ass.py）筛选底部弹幕的原理是正则匹配并删除所有带 move 的行和所有纵坐标在540以上的弹幕行（为了剔除顶部弹幕），所以如要直接使用本程序，❗使用弹幕盒子转换前，应先将基础参数里的视频高度设置为1080❗** .

否则您应先自行修改process_ass.py 第6行的正则匹配式再运行使用。

6. 运行ass文件同目录下的 process_ass.py （在本仓库下载）。即可一步完成提取底部弹幕作为字幕转换成lrc字幕。lrc文件会生成在当前目录。而程序会保留正则替换筛选后的ass文件到“替换后ass文件夹”。

程序运行后的一个典型的文件结构示例如下：
```
.
├── .ass                   (原本的全弹幕文件)
├── 🎵.lrc                 (最终转换成的字幕文件)
├── 🐍 process_ass.py      (⭐本程序)
└── 📁 替换后ass/          (程序自动生成的文件夹，存放中间步骤的ASS文件)
    └── .ass                  (仅底部弹幕的ASS文件)
```

🎉🎉🎉由xml弹幕经筛选提取的字幕lrc生成成功！
