<div align="center">

# 🎵 Bilibili VC

**B站 VOCALOID / 虚拟歌手 视频数据工作流工具**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Bilibili](https://img.shields.io/badge/Bilibili-API-E0672A)](https://github.com/fython/BilibiliAPIDocs)

*从采集、筛选、批量采集、算分到云服务器分发——面向 B站虚拟歌手领域的全自动化数据工作流*

</div>

---

## 📖 项目简介

**Bilibili VC** 是一个面向 B 站 **VOCALOID·UTAU**（分区 ID=30）及虚拟歌手（Vsinger）领域的视频数据自动化处理工具集。

为周刊运营者 / 数据分析爱好者提供一套完整的工作流：

1. **📥 自动采集** — 增量爬取分区最新视频到本地数据库
2. **🔍 智能筛选** — 按时长、关键词、屏蔽词、黑名单筛选目标视频
3. **🚀 批量采集** — 多线程并发获取 BV 号的完整播放数据
4. **☁️ 云端分发** — 切片分发到云服务器并行采集，加速大规模数据处理
5. **📊 增量算分** — 对比两个时间点数据，多维修正公式计算综合得分
6. **⭐ 自动收藏** — 将算分结果前 N 个视频一键加入 B站收藏夹
7. **🎵 下载 MP3** — 将算分结果前 N 个视频的音频下载到本地
8. **☁️ 同步网易云** — 将下载的 MP3 上传至网易云云盘并创建歌单

---

## 🗂️ 项目结构

```
bilibili_vc/
├── script/                          # 📁 核心脚本目录
│   ├── bilibili_search.py           #   核心库：Bilibili API 客户端
│   ├── crawl_to_db.py               #   增量采集器：分区视频 → SQLite
│   ├── filter.py                    #   筛选器：时长 + 关键词 + 黑名单
│   ├── bv_fetcher.py                #   批量采集器：多线程并发获取数据
│   ├── slice_and_merge.py           #   切片 & 合并：BV 号分布 + 结果归并
│   ├── score_diff.py                #   增量算分器：两时间点对比 → 综合得分
│   ├── add_to_fav.py                #   B站收藏夹工具：算分结果加入收藏夹
│   ├── download_mp3.py              #   MP3 下载 + 网易云同步
│   ├── ncm_utils.py                 #   网易云 Node.js 操作封装
│   ├── ncm_delete.py               #   删除网易云歌单和云盘音乐
│   ├── main.py                      #   交互式工作流总控
│   ├── startserver.py               #   腾讯云 CVM 实例创建
│   ├── check_instance.py            #   腾讯云 CVM 检查/销毁
│   ├── upload.py                    #   SSH/SCP 文件上传
│   ├── download.py                  #   SSH/SCP 文件下载
│   ├── single.py                    #   单视频快速查询示例
│   ├── setup_and_run.sh             #   远程服务器初始化脚本
│   └── netease/                     # 📁 网易云 JS 子项目
│       ├── package.json             #   NPM 依赖声明
│       ├── upload_to_cloud.js       #   上传 MP3 到云盘
│       ├── sync_to_playlist.js      #   创建歌单 + 添加歌曲
│       ├── delete_playlist.js       #   删除歌单
│       └── delete_uploaded.js       #   删除云盘音乐
│
├── workspace/                       # 📁 所有生成数据存放目录
│   ├── bilibili_videos.db           #   原始视频数据库
│   ├── filtered_videos.db           #   筛选后的目标视频库
│   ├── crawl_progress.json          #   采集进度记录
│   ├── instances_info.json          #   云服务器实例信息
│   ├── blacklist.txt                #   BV 号黑名单
│   ├── slice_*.txt                  #   切片后的 BV 号列表
│   ├── result_*.xlsx                #   批量采集结果
│   ├── *_failed.txt                 #   采集中失败的 BV 号
│   ├── bilibili_cookies.json        #   B站登录 Cookie（首次收藏时生成）
│   └── downloaded_mp3/              # 📁 下载的 MP3 文件 + manifest.json
│
├── .gitignore
└── README.md
```

---

## 🚀 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/sunny-luoyun/bilibili_vc.git
cd bilibili_vc

# 安装依赖（核心）
pip install openpyxl
pip install mutagen                 # MP3 ID3 标签写入
pip install yt-dlp                  # B站音频下载

# 可选依赖（按需安装）
pip install paramiko                # SSH 上传/下载到云服务器
pip install tencentcloud-sdk-python # 腾讯云 CVM 自动管理

# 网易云所需（如果使用功能12/13）
# 需要安装 Node.js (>=12)，首次运行会自动 npm install
```

### 交互式工作流

```bash
cd script
python main.py
```

菜单界面操作（输入数字选择）：

```
===== 周刊工作流管理程序 =====
 1.  采集视频                    # crawl_to_db.py
 2.  筛选视频                    # filter.py
 3.  切片BV号                    # 内置切片
 4.  创建云服务器                 # startserver.py
 5.  上传数据到服务器              # 自动分发
 6.  生成远程采集命令              # SSH 命令
 7.  下载服务器结果                # 批量下载
 8.  合并结果文件                  # 内置合并
 9.  计算得分                     # score_diff.py
10.  删除所有服务器                # check_instance.py
11.  算分结果加入收藏夹             # add_to_fav.py
12.  下载MP3 → 上传网易云 → 创建歌单  # download_mp3.py + netease/
13.  删除网易云歌单和云盘音乐         # ncm_delete.py
 0.  退出
```

---

## ⚙️ 配置指南

### 默认分区

项目默认采集 `tid=30`（VOCALOID·UTAU），通过 `--tid` 参数修改：

```bash
python crawl_to_db.py --tid 36   # 改为采集"知识"分区
```

### 筛选关键词

编辑 `script/filter.py` 中的 `KEYWORDS` 和 `BLOCK_KEYWORDS` 列表：

```python
KEYWORDS = [
    "洛天依", "天依", "乐正绫", "言和", "乐正龙牙",
    "墨清弦", "徵羽摩柯", "心华", "星尘", "海伊",
    "苍穹", "赤羽", "诗岸", "牧心", "艾尔法", "永夜",
    "初音未来"
]
```

### SSH 凭据

`main.py` 中内置默认凭据，可在交互式菜单中按需修改：

- 默认用户名：`ubuntu`
- 默认密码：`X#7kPm$9qL@2wR&`
- 默认远程目录：`/home/ubuntu/`

---

## 📁 数据文件说明

| 文件 | 路径 | 说明 |
|------|------|------|
| 原始视频数据库 | `workspace/bilibili_videos.db` | `crawl_to_db.py` 的采集结果 |
| 筛选视频库 | `workspace/filtered_videos.db` | `filter.py` 的筛选结果 |
| 采集进度 | `workspace/crawl_progress.json` | 固定页码模式下的断点续爬记录 |
| 实例信息 | `workspace/instances_info.json` | 云服务器实例信息 |
| 黑名单 | `workspace/blacklist.txt` | BV 号黑名单（每行一个） |
| 切片文件 | `workspace/slice_*.txt` | 切片后的 BV 号列表 |
| 采集结果 | `workspace/result_*.xlsx` | 批量采集结果 |
| 失败记录 | `workspace/*_failed.txt` | 批量采集中失败的 BV 号 |
| 密钥文件 | `./credentials.json` | 腾讯云 API 密钥（需自行创建） |
| B站 Cookie | `workspace/bilibili_cookies.json` | 自动收藏功能生成的 B站登录凭证 |
| MP3 文件 | `workspace/downloaded_mp3/` | 功能 12 下载的 MP3 音频 |
| 网易云 Cookie | `script/netease/.ncm_cookie` | 网易云扫码登录 Cookie（自动管理） |
| 上传记录 | `script/netease/.ncm_history.json` | 已上传到云盘的文件记录 |
| 歌单记录 | `script/netease/.ncm_playlist_id` | 已创建的网易云歌单 ID |

---

## ⭐ 自动收藏

将算分结果中的高分视频一键加入你的 B站收藏夹。

```bash
# 命令行直接使用
python script/add_to_fav.py score/20260513_14-20260516_09.xlsx --top 10

# 或通过交互菜单（选 11）
python script/main.py
```

**首次使用**需要提供 B站 Cookie（`SESSDATA` + `bili_jct`）：
1. 浏览器登录 [bilibili.com](https://www.bilibili.com)
2. 按 `F12` → **Application** → Cookies → `https://www.bilibili.com`
3. 复制 `SESSDATA`、`bili_jct` 和 `DedeUserID` 的值
4. 粘贴到终端提示中，脚本会自动保存到 `workspace/bilibili_cookies.json`（后续复用）

**流程：** 选择算分文件 → 输入前 N 名数量 → 输入收藏夹名称（自动新建）→ 逐个添加到收藏夹 → 输出成功/失败列表

---

## 🎵 下载 MP3 & 同步网易云云盘

将算分结果前 N 个视频下载为 MP3，并上传至网易云云盘、创建歌单（功能 12）。

```bash
# 命令行直接使用
python script/download_mp3.py score/20260513_14-20260516_09.xlsx --top 10

# 仅下载不上传
python script/download_mp3.py score/xxx.xlsx --top 10 --download-only

# 仅执行网易云操作（跳过下载）
python script/download_mp3.py --ncm-only

# 通过交互菜单（选 12）
python script/main.py
```

**流程：** 选择算分文件 → 输入前 N 名 → 自动下载（yt-dlp + FFmpeg 转 MP3）→ 写入 ID3 标签 → 上传网易云云盘 → 创建歌单并添加歌曲

**首次使用网易云**需扫码登录：
1. 脚本会生成 `qrcode.png` 二维码文件
2. 打开网易云音乐 App → 扫一扫
3. 登录成功后 Cookie 自动保存，后续复用

### 删除网易云歌单和云盘音乐（功能 13）

```bash
# 通过交互菜单（选 13）
python script/main.py

# 或命令行
python script/ncm_delete.py
```

---

## 🧪 环境要求

- **Python** 3.8+
- **系统** macOS / Linux / Windows
- **Node.js** ≥12（仅功能 12/13，网易云 API 交互）
- **FFmpeg**（功能 12，yt-dlp 转 MP3 需要）
- **依赖**（按需）：
  - `openpyxl` — Excel 文件读写
  - `paramiko` — SSH 文件传输
  - `tencentcloud-sdk-python` — 腾讯云 CVM
  - `yt-dlp` — B 站音频下载
  - `mutagen` — MP3 ID3 标签写入

---


## 🙏 致谢

- [BilibiliAPIDocs](https://github.com/fython/BilibiliAPIDocs) — B 站 API 文档参考
- [寒棠 Daily](https://github.com/hantang-daily) — 批量采集器实现思路参考


---

<div align="center">
Made with ❤️ for the VOCALOID community
</div>
