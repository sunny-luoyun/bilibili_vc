<div align="center">

# 🎵 Bilibili VC

**B站 VOCALOID/虚拟歌手 视频采集工作流工具**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*从采集、筛选、批量采集数据、算分到云服务器分发——全自动化的 B站虚拟歌手视频数据工作流*

</div>

---

## 📖 项目简介

**Bilibili VC** 是一个面向 B 站 **VOCALOID·UTAU**（分区 ID=30）及虚拟歌手（Vsinger）领域的视频数据自动化处理工具集。项目提供一套完整的工作流，帮助运营者/爱好者：

1. 自动采集指定分区的最新视频到**本地数据库**
2. 按**时长、关键词、黑名单**筛选目标视频
3. 将 BV 号**批量分发**到多台云服务器并行采集详细数据
4. 计算两个时间点之间的**增量得分**，生成排行榜/周刊


---

## 🏗️ 项目架构

```
bilibili_vc/
├── bilibili_search.py      # 核心库：Bilibili API 客户端（分区搜索、关键词搜索、WBI 签名）
├── crawl_to_db.py          # 增量采集器：分区视频 → SQLite 数据库
├── filter.py               # 筛选器：时长 + 关键词 + 黑名单过滤
├── bv_fetcher.py           # 批量采集器：多线程并发获取 BV 号的完整数据
├── slice_and_merge.py      # 切片 & 合并工具：BV 号分片 + 结果合并
├── score_diff.py           # 增量算分器：两时间点对比 → 综合得分
├── main.py                 # 交互式工作流总控：菜单驱动全流程
├── startserver.py          # 腾讯云 CVM 实例创建
├── check_instance.py       # 腾讯云 CVM 实例检查/销毁
├── upload.py               # SSH/SCP 文件上传工具
├── download.py             # SSH/SCP 文件下载工具
├── single.py               # 单视频快速查询示例
├── setup_and_run.sh        # 远程服务器初始化脚本
└── .gitignore
```

---

## 🚀 快速开始

### 安装依赖

```bash
pip install openpyxl paramiko tencentcloud-sdk-python
```

> **可选依赖**（按需安装）：
> - `paramiko` — SSH 上传/下载文件到云服务器
> - `tencentcloud-sdk-python` — 腾讯云 CVM 自动创建/管理
> - `openpyxl` — Excel 文件读写

### 基础工作流

完整的工作流分为以下步骤，你可以通过 `main.py` 的交互式菜单逐步执行，也可以单独调用每个脚本：

```bash
python main.py
```

然后按照菜单提示操作（数字选择）：

```
===== 周刊工作流管理程序 =====
1.  采集视频           # crawl_to_db.py
2.  筛选视频           # filter.py
3.  切片BV号           # slice_and_merge.py --mode slice
4.  创建云服务器       # startserver.py
5.  上传数据到服务器
6.  生成远程采集命令
7.  下载服务器结果
8.  合并结果文件       # slice_and_merge.py --mode merge
9.  计算得分           # score_diff.py
10. 删除所有服务器     # check_instance.py
0.  退出
```

---

## 📦 模块详解

### 1️⃣ `bilibili_search.py` — Bilibili API 客户端

核心库，封装了 B 站公开 API 的全部搜索与获取功能：

| 功能 | 方法 | 说明 |
|------|------|------|
| 分区最新视频 | `get_newlist(tid, page, order)` | 按分区获取最新投稿 |
| 分区排行榜 | `get_ranking(tid)` | 获取分区热门排行 |
| 关键词搜索 | `search(keyword, tid, ...)` | 在分区内/全站搜索 |

**特性**：
- 内置 WBI 签名机制，无需 appKey
- 自动 gzip 解压、SSL 处理
- 完备的分区映射表（`PARTITION_MAP`，含 50+ 分区）
- 支持多种排序：发布时间 / 播放量 / 收藏 / 硬币 / 弹幕 / 点赞

```python
from bilibili_search import BilibiliClient

client = BilibiliClient(delay=1.0)
result = client.get_newlist(tid=30, page=1, order="pubdate")
for video in result["videos"]:
    print(f"[{video.bvid}] {video.title} - {video.author}")
```

**预置分区映射（部分）**：

| tid | 分区名 |
|-----|--------|
| 30 | VOCALOID·UTAU |
| 3 | 音乐 |
| 36 | 知识 |
| 4 | 游戏 |
| 24 | MAD·AMV |

### 2️⃣ `crawl_to_db.py` — 分区视频增量采集入库

自动采集指定分区的视频并存储到 SQLite 数据库（`bilibili_videos.db`）。

**采集策略**：
- **增量模式**（默认）：从第 1 页开始采集，遇到所有视频已入库时自动停止
- **固定页码模式**（`--page`）：从指定页码开始采集固定页数，支持断点续爬

```bash
# 增量采集分区 tid=30（默认）
python crawl_to_db.py

# 指定分区、最多检查 50 页
python crawl_to_db.py --tid 30 --max-pages 50

# 指定水位线时间（从该时间向前采集）
python crawl_to_db.py --since "2026-01-01 00:00"

# 强制从第 10 页开始采集 5 页
python crawl_to_db.py --page 10 --max-pages 5
```

**反爬保护**：
- 请求间隔 ≥ 3.5 秒（~17次/分钟，远低于 20 次限制）
- 412 错误自动重试 + 长等待（65秒）
- 空结果重试机制，防止网络波动误判

### 3️⃣ `filter.py` — 视频筛选

从 `bilibili_videos.db` 中筛选符合条件的目标视频，输出到 `filtered_videos.db`。

**筛选条件**：
- ✅ **时长**：默认 2~7 分钟（可配）
- ✅ **关键词**：标题或简介包含以下关键词（可编辑）：

```
洛天依, 乐正绫, 言和, 乐正龙牙, 墨清弦, 徵羽摩柯,
心华, 星尘, 海伊, 赤羽, 诗岸, 初音未来 ...
```

- ❌ **屏蔽词**：排除周刊类、搬运类内容
- ❌ **黑名单**：从 `blacklist.txt` 读取要排除的 BV 号

**额外功能**：自动备份上次筛选结果并输出**新增视频对比**。

```bash
# 默认筛选（时长 2~7 分钟）
python filter.py

# 自定义时长和黑名单文件
python filter.py --min 180 --max 600 --blacklist exclude.txt
```

### 4️⃣ `bv_fetcher.py` — BV 号批量数据采集器

多线程并发采集工具，从 B 站 view 接口批量获取视频的完整播放数据。

**输入**：txt/csv/xlsx/数据库文件（每行一个 BV 号或 B 站链接）

**输出**：csv/xlsx/json（包含播放量、弹幕、评论、收藏、硬币、点赞等详细统计）

**特性**：
- 10 线程并发，每批 100 个 BV 号
- 随机 User-Agent 防反爬
- 指数退避重试
- 实时进度条
- 失败 BV 号单独记录到 `*_failed.txt`

```bash
# 从文件读取 BV 号列表
python bv_fetcher.py -i bv_list.txt -o result.xlsx

# 从 SQLite 数据库直接读取
python bv_fetcher.py -i filtered_videos.db -o result.xlsx

# 安静模式（仅进度条）
python bv_fetcher.py -i input.txt --quiet

# 自定义线程数
python bv_fetcher.py -i input.txt -w 20
```

### 5️⃣ `slice_and_merge.py` — 切片 & 合并

三种工作模式：

| 模式 | 说明 |
|------|------|
| `--mode slice` | 将数据库中的 BV 号平均分为 N 份（默认 3 份），生成 txt 文件 |
| `--mode merge` | 将多个结果文件合并为一个（去重保留最新） |
| `--mode auto` | 本地自动切片 → 并行采集 → 合并（单机多进程加速） |

```bash
# 切片（分3份）
python slice_and_merge.py --mode slice --source filtered_videos.db

# 合并3个结果文件
python slice_and_merge.py --mode merge \
  --result1 out1.xlsx --result2 out2.xlsx --result3 out3.xlsx \
  --out merged.xlsx

# 全自动模式：切片→并行采集→合并
python slice_and_merge.py --mode auto \
  --source filtered_videos.db --out merged.xlsx
```

### 6️⃣ `score_diff.py` — 增量算分

对比两个时间点的数据文件，计算每个视频的增量指标，并按照自定义公式计算综合得分。

**得分公式**：

```
最终得分 = 播放得分 + 互动得分 + 收藏得分 + 硬币得分 + 点赞得分
```

每个子项引入了多重修正因子（修正A~D），综合考虑播放量、互动率、收藏/硬币比等多维数据，防止数据注水。

```bash
# 比较两个时间点的数据
python score_diff.py data_20260510.xlsx data_20260511.xlsx

# 指定输出文件
python score_diff.py old.xlsx new.xlsx -o diff_result.xlsx
```

### 7️⃣ 云服务器管理

| 脚本 | 功能 |
|------|------|
| `startserver.py` | 自动创建腾讯云 CVM 实例（南京区、Ubuntu、按量计费） |
| `check_instance.py` | 查询/销毁已创建的实例 |
| `upload.py` | 上传文件到公网服务器（paramiko） |
| `download.py` | 从公网服务器下载文件（paramiko） |
| `setup_and_run.sh` | 远程服务器初始化脚本（安装依赖 + 启动采集） |

> ⚠️ 使用前需在项目根目录创建 `credentials.json`：
> ```json
> {
>   "secret_id": "你的腾讯云 SecretId",
>   "secret_key": "你的腾讯云 SecretKey"
> }
> ```

---


## ⚙️ 配置指南

### 默认分区

项目默认采集 `tid=30`（VOCALOID·UTAU），可通过 `--tid` 参数修改：

```bash
python crawl_to_db.py --tid 36   # 改为采集"知识"分区
```

### 关键词定制

编辑 `filter.py` 中的 `KEYWORDS` 和 `BLOCK_KEYWORDS` 列表即可自定义筛选条件。

### 算分公式调整

`score_diff.py` 中的 `calc_scores()` 函数实现了完整的评分逻辑，可根据需求调整各子项的权重和修正因子。

---

## 📁 数据文件说明

| 文件 | 说明 |
|------|------|
| `bilibili_videos.db` | 原始视频数据库（采集结果） |
| `filtered_videos.db` | 筛选后的目标视频库 |
| `crawl_progress.json` | 采集进度记录（断点续爬用） |
| `instances_info.json` | 云服务器实例信息 |
| `blacklist.txt` | BV 号黑名单（每行一个） |
| `slice_*.txt` | 切片后的 BV 号列表 |
| `result_*.xlsx` | 批量采集结果 |
| `*_failed.txt` | 批量采集中失败的 BV 号 |
| `credentials.json` | 腾讯云 API 密钥（需自行创建） |

---

## 🧪 环境要求

- Python 3.8+
- macOS / Linux / Windows
- 依赖包（按需）：
  - `openpyxl` — Excel 操作
  - `paramiko` — SSH 文件传输
  - `tencentcloud-sdk-python` — 腾讯云 CVM

---

## 📝 注意事项

1. **API 频率限制**：B 站 API 有频率限制（约 20 次/分钟），脚本已内置请求间隔和退避机制
2. **412 错误**：触发风控后脚本会自动等待 ~65 秒后重试
3. **SSL 问题**：macOS Python 3.12+ 可能需要设置 `--no-ssl-check` 或在代码中禁用 SSL 验证
4. **云服务器成本**：使用腾讯云 CVM 需注意按量计费的持续费用，用后及时销毁

---

## 🙏 致谢

- [BilibiliAPIDocs](https://github.com/fython/BilibiliAPIDocs) — B 站 API 文档参考
- [寒棠 Daily](https://github.com/hantang-daily) — 批量采集器实现思路参考

---

## 📄 许可证

[MIT](LICENSE)

---

<div align="center">
Made with ❤️ for the VOCALOID community
</div>
