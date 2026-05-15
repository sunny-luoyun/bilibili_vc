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
│   ├── main.py                      #   交互式工作流总控
│   ├── startserver.py               #   腾讯云 CVM 实例创建
│   ├── check_instance.py            #   腾讯云 CVM 检查/销毁
│   ├── upload.py                    #   SSH/SCP 文件上传
│   ├── download.py                  #   SSH/SCP 文件下载
│   ├── single.py                    #   单视频快速查询示例
│   └── setup_and_run.sh             #   远程服务器初始化脚本
│
├── workspace/                       # 📁 所有生成数据存放目录
│   ├── bilibili_videos.db           #   原始视频数据库
│   ├── filtered_videos.db           #   筛选后的目标视频库
│   ├── crawl_progress.json          #   采集进度记录
│   ├── instances_info.json          #   云服务器实例信息
│   ├── blacklist.txt                #   BV 号黑名单
│   ├── slice_*.txt                  #   切片后的 BV 号列表
│   ├── result_*.xlsx                #   批量采集结果
│   └── *_failed.txt                 #   采集中失败的 BV 号
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

# 可选依赖（按需安装）
pip install paramiko                # SSH 上传/下载到云服务器
pip install tencentcloud-sdk-python # 腾讯云 CVM 自动管理
```

### 交互式工作流

```bash
cd script
python main.py
```

菜单界面操作（输入数字选择）：

```
===== 周刊工作流管理程序 =====
 1.  采集视频            # crawl_to_db.py
 2.  筛选视频            # filter.py
 3.  切片BV号            # 内置切片
 4.  创建云服务器         # startserver.py
 5.  上传数据到服务器      # 自动分发
 6.  生成远程采集命令      # SSH 命令
 7.  下载服务器结果        # 批量下载
 8.  合并结果文件          # 内置合并
 9.  计算得分             # score_diff.py
10.  删除所有服务器        # check_instance.py
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

---

## 🧪 环境要求

- **Python** 3.8+
- **系统** macOS / Linux / Windows
- **依赖**（按需）：
  - `openpyxl` — Excel 文件读写
  - `paramiko` — SSH 文件传输
  - `tencentcloud-sdk-python` — 腾讯云 CVM

---

## 📝 注意事项

1. **API 频率限制**：B 站 API 约 20 次/分钟，脚本已内置请求间隔 + 退避机制
2. **412 风控**：触发后自动等待 ~65 秒重试
3. **SSL 证书**：macOS Python 3.12+ 可能需要跳过 SSL 验证（脚本内已处理）
4. **云服务器成本**：按量计费实例用后及时销毁，避免持续扣费
---


## 🙏 致谢

- [BilibiliAPIDocs](https://github.com/fython/BilibiliAPIDocs) — B 站 API 文档参考
- [寒棠 Daily](https://github.com/hantang-daily) — 批量采集器实现思路参考


---

<div align="center">
Made with ❤️ for the VOCALOID community
</div>
