#!/usr/bin/env python3
"""
从 B 站视频标题中智能提取歌名
============================

用法:
  python extract_song_name.py "【洛天依原创】我的悲伤是水做的"
  python extract_song_name.py --file titles.txt       # 每行一个标题
  python extract_song_name.py --excel score.xlsx      # 读取算分 Excel 的 title 列

提取策略（按优先级）:
  1. 《》 → 百分百歌名
  2. 「」→ 次可靠
  3. ⚡⚡ → 装饰符包裹
  4. 剥离【】后，取剩余文本中的有效歌名
"""

import re
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 歌手关键词（按长度降序，避免短词误匹配）
ARTIST_KEYWORDS = sorted([
    "洛天依", "天依", "乐正绫", "言和", "乐正龙牙", "墨清弦", "徵羽摩柯",
    "心华", "星尘", "海伊", "苍穹", "赤羽", "诗岸", "牧心", "艾尔法", "永夜",
    "初音未来",
], key=len, reverse=True)


def detect_artist(title: str) -> str:
    """从标题中检测第一个匹配的歌手名"""
    for name in ARTIST_KEYWORDS:
        if name in title:
            return name
    return ""


def extract_song_name(title: str) -> str:
    """
    从 B 站视频标题中提取歌名，返回最可能的歌名（去掉装饰 & 后缀）。
    若无法提取，返回原标题的简洁版本。
    """
    if not title:
        return ""

    original = title
    # 统一引号：弯引号 → 直引号
    title = title.replace('\u201c', '"').replace('\u201d', '"')
    title = title.replace('\u2018', "'").replace('\u2019', "'")

    # ── 优先级 1: 《》→ 取第一个匹配 ──
    m = re.search(r'《([^》]+)》', title)
    if m:
        return m.group(1).strip()

    # ── 优先级 2: 「」→ 取第一个匹配 ──
    m = re.search(r'「([^」]+)」', title)
    if m:
        return m.group(1).strip()

    # ── 优先级 3: ⚡⚡ 装饰符包裹 ──
    m = re.search(r'⚡([^⚡]+)⚡', title)
    if m:
        return m.group(1).strip()

    # ── 优先级 4: 先剥离所有【】标签 ──
    stripped = re.sub(r'【[^】]*】', '', title).strip()

    # 特殊 #28: `/ lyrics /【】song_name` → 取【】后的文本
    if re.search(r'【[^】]*】', title):
        after_last = re.sub(r'^.*【[^】]*】', '', title).strip()
        if after_last:
            before_first = re.sub(r'【[^】]*】.*$', '', title).strip()
            # 如果【】前有 / 包裹的歌词，且【】后有文本 → 取后面
            if re.match(r'^/', before_first) and '/' in before_first:
                stripped = after_last

    # 去掉末尾装饰: (得分:...)、（PV工期...）等
    cleaned = re.sub(r'[（(][^）)]*[)）]', '', stripped).strip()
    cleaned = re.sub(r'\[[^\]]*\]', '', cleaned).strip()

    # ── 处理 "..." 引号 ──
    # pattern: text_before"..."text_after
    qm = re.match(r'^(.*?)[""]([^""]*)[""](.*)$', cleaned)
    if qm:
        before = qm.group(1).strip()
        inside = qm.group(2).strip()
        after = qm.group(3).strip()
        if before and not after:
            # Case #4: 想"..." → 想 is the song name
            cleaned = before
        elif not before and not after:
            # Case #47: "我们在泪海的两端..." → inside is the song name
            cleaned = inside
        elif not before and after:
            # Case #18: "终于学会..."星尘原创/叙梦 → process `after`
            cleaned = after
        else:
            # both before and after exist — remove quotes, keep both sides
            cleaned = (before + ' ' + after).strip()
    else:
        # 无引号，但有其他引号残留
        cleaned = cleaned.replace('"', '').replace('"', '').strip()

    # ── 按 || 或 | 切分，取第一段 ──
    if '||' in cleaned or '|' in cleaned:
        parts = re.split(r'\|\|?\s*', cleaned)
        cleaned = parts[0].strip()

    # ── 处理 Feat./feat. ──
    cleaned = re.sub(r'\s+Feat\.?\s*.*', '', cleaned, flags=re.I).strip()

    # ── 按 / 切分：取有效段（非空、非明显歌词/标签） ──
    if '/' in cleaned:
        parts = [p.strip() for p in cleaned.split('/')]
        parts = [p for p in parts if p]
        if parts:
            if len(parts) == 1:
                cleaned = parts[0]
            elif len(parts[0]) <= 3:
                # 第一段很短（如 迷 /立入禁止）→ 取第一段
                cleaned = parts[0]
            elif re.search(r'(原创|翻唱|翻调|中文填词|填词|Cover)$', parts[0], re.I):
                # 第一段是标签（如 星尘原创/叙梦）→ 取最后一段
                cleaned = parts[-1]
            else:
                cleaned = parts[0]

    # 去掉开头的 洛天依/乐正绫/原创 等前缀
    cleaned = re.sub(
        r'^(洛天依[，,、]?\s*|乐正绫[，,、]?\s*|言和[，,、]?\s*'
        r'|星尘[，,、]?\s*|诗岸[，,、]?\s*|墨清弦[，,、]?\s*'
        r'|赤羽[，,、]?\s*|苍穹[，,、]?\s*|海伊[，,、]?\s*'
        r'|歌愛ユキ[，,、]?\s*|奕夕[，,、]?\s*'
        r'|Vsinger\s*|原创\s*)',
        '', cleaned
    ).strip()

    # 去掉句尾的 Remake ver./Solo Ver./Long ver. 等版本标记
    cleaned = re.sub(
        r'\s+(Remake\s*ver\.?|Solo\s*Ver\.?|Long\s*ver\.?|ver\.?\s*\d*)$',
        '', cleaned, flags=re.I
    ).strip()

    # 去掉两侧 · 。、，, 等标点
    cleaned = cleaned.strip('·。、，, ')

    # 去掉尾部 原创/翻唱/翻调/填词
    cleaned = re.sub(r'(原创|翻唱|翻调|中文填词|填词)\s*$', '', cleaned).strip()

    # 去掉 —— 及之后内容
    cleaned = re.split(r'[—–]{2,}', cleaned)[0].strip()

    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    if cleaned:
        return cleaned

    return original


def preprocess_line(line: str) -> str:
    """从 `序号. [BVxxx] 标题 (得分: xxx)` 中提取纯标题"""
    line = line.strip()
    # 去掉行首的序号，如 "1. " "  22. "
    line = re.sub(r'^\s*\d+\.?\s*', '', line)
    # 去掉 [BV...] 或 [av...] 等媒体ID（字母+数字混合）
    line = re.sub(r'\[[a-zA-Z]{2}[a-zA-Z0-9]+\]\s*', '', line)
    # 去掉末尾 (得分: ...)
    line = re.sub(r'\s*[（(]得分[：:]\s*[\d,.]+[)）]\s*$', '', line)
    # 去掉末尾 (score: ...)
    line = re.sub(r'\s*[（(]score[：:]\s*[\d,.]+[)）]\s*$', '', line, flags=re.I)
    return line.strip()


def test():
    """用 50 条示例验证提取效果"""
    titles = [
        (1, '"还有我 在你身边说我爱你啊"洛天依《蝴蝶》【原创手书PV】', '蝴蝶'),
        (2, '【诗岸】迷 /立入禁止', '迷'),
        (3, '"受天命伐四方 览不尽盛世无双"洛天依原创曲《破天光》【国乐季·鼓乐篇】', '破天光'),
        (4, '【洛天依原创中考应援曲】想"要怎样才能学会精准计算，人生最完美最精确的答案。"', '想'),
        (5, '【墨清弦原创曲】月色清弦【2026官方生贺曲】', '月色清弦'),
        (6, '【乐正绫ACE原创】你是我爱这世界的原因【绫号宇宙/HB to 斜日红狐泽】', '你是我爱这世界的原因'),
        (7, '【星尘/诗岸/原创摇滚】反乌托邦 "至少我还在为你而歌唱，在黑暗漫长的反乌托邦"', '反乌托邦'),
        (8, '洛天依 原创《告死鸟》', '告死鸟'),
        (9, '【三角洲群像】 ⚡Counting Stars⚡ 请选择你的干员', 'Counting Stars'),
        (10, '求婚 / プロポーズ 中文填词【诗岸】【内緒のピアス】', '求婚'),
        (11, '《反乌托邦Pt.2 》洛天依Solo Ver.', '反乌托邦Pt.2'),
        (12, '塞德娜    Feat.星尘', '塞德娜'),
        (13, '客官请留步❀~与墨共饮《八宝琳琅》一盏收【墨清弦八周年】【VC八人PV付】', '八宝琳琅'),
        (14, '【洛天依原创】《Liar Game》feat.重音テト//"面具之外，还是面具……"', 'Liar Game'),
        (15, '【洛天依原创】我的悲伤是水做的', '我的悲伤是水做的'),
        (16, '洛天依，原创《勾指起誓》', '勾指起誓'),
        (17, '【赤羽粤语翻唱】一格格【HB to Creuzer】', '一格格'),
        (18, '"终于学会飞行，却得知天空是假的"星尘原创/叙梦', '叙梦'),
        (19, '【乐正绫】混入人类计划【HB to Creuzer】【ACE V COVER】', '混入人类计划'),
        (20, '富贵险中求？有账有好友！❖墨的《八字只求财》【墨清弦八周年】【Vsinger全员付】', '八字只求财'),
        (21, '【洛天依原创】《歌》', '歌'),
        (22, '【乐正绫原创曲】比绫星（pv工期中待换源）', '比绫星'),
        (23, '【洛天依言和原创】斯芬克斯之谜', '斯芬克斯之谜'),
        (24, '《崩坏：星穹铁道》三周年·全角色填词PV「Counting Stars」', '崩坏：星穹铁道'),
        (25, '【赤羽/苍穹原创】千载秦声【忘川风华录同人 · 大秦群像】', '千载秦声'),
        (26, '【奕夕/重音テト/中文填词翻调】ANOTHER CUP || 😭永远喝不到嘴的咖啡😭', 'ANOTHER CUP'),
        (27, '【洛天依原创】伤心的话说一遍就够', '伤心的话说一遍就够'),
        (28, '/ 公平是荒诞的幻觉  你是注定的进献 /【洛天依·言和原创曲】我唯一的孩子', '我唯一的孩子'),
        (29, '【洛天依原创/小清新国风】追月谣（半木生工作室）', '追月谣'),
        (30, '【言和】《牵丝戏》（重调版）|"唱别久悲不成悲，十分红处竟成灰"【原创PV付】', '牵丝戏'),
        (31, '【高考应援/星尘诗岸】前往六月乌托邦 Remake ver."六月乌托邦 等你续写晚霞"', '前往六月乌托邦'),
        (32, '洛天依原创《开天》·不过三尺三。', '开天'),
        (33, '洛天依 原创《白鸟过河滩》', '白鸟过河滩'),
        (34, '【洛天依原创PV付】失温症', '失温症'),
        (35, '【苍穹原创】木兰行【忘川风华录】', '木兰行'),
        (36, '【洛天依乐正绫原创】错姑苏', '错姑苏'),
        (37, '【星尘原创】每个远方', '每个远方'),
        (38, '太阳是什么颜色【2026乐正绫官方生贺曲】', '太阳是什么颜色'),
        (39, '【李商隐】梦间花（海伊）', '梦间花'),
        (40, '洛天依，言和原创《普通DISCO》', '普通DISCO'),
        (41, '【洛天依古风原创曲】权御天下【原创PV付】', '权御天下'),
        (42, '【洛天依】下等马', '下等马'),
        (43, '【洛天依原创】那就当我们没认识过吧', '那就当我们没认识过吧'),
        (44, '【诗岸/摇滚】山雨', '山雨'),
        (45, '【乐正绫原创】世末歌者【PV付/COSMOSⅡ】', '世末歌者'),
        (46, '史铁生的《哪里都去不了》【中文填词/诗岸】', '哪里都去不了'),
        (47, '【洛天依原创】"我们在泪海的两端，越靠近越是不安"', '我们在泪海的两端，越靠近越是不安'),
        (48, '【歌愛ユキ/诗岸】惊蛰正中央/立入禁止', '惊蛰正中央'),
        (49, '【诗岸/艾可原创曲】彼岸花 (Long ver.)【本家】', '彼岸花'),
        (50, '未来会来的，别怕——【墨清弦八周年生贺原创】', '未来会来的，别怕'),
    ]

    print(f"{'#':>3} | {'期望':<30} | {'实际':<30} | {'标题'}")
    print(f"{'-'*3}-+-{'-'*30}-+-{'-'*30}-+-{'-'*50}")
    pass_count = 0
    for idx, title, expected in titles:
        result = extract_song_name(title)
        ok = "✓" if result == expected else "✗"
        if ok == "✓":
            pass_count += 1
        print(f"{ok} {idx:>2} | {expected:<30} | {result:<30} | {title[:50]}")
    total = len(titles)
    print(f"\n通过: {pass_count}/{total} ({pass_count / total * 100:.0f}%)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n示例:")
        print(f"  python {os.path.basename(__file__)} --test")
        print(f'  python {os.path.basename(__file__)} "【洛天依原创】我的悲伤是水做的"')
        return

    if sys.argv[1] == "--test":
        test()
        return

    if sys.argv[1] == "--file":
        filepath = sys.argv[2]
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    title = preprocess_line(line)
                    song = extract_song_name(title)
                    print(song)
        return

    if sys.argv[1] == "--excel":
        filepath = sys.argv[2]
        try:
            import openpyxl
        except ImportError:
            print("需要 openpyxl: pip install openpyxl")
            sys.exit(1)
        wb = openpyxl.load_workbook(filepath, read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
        if len(rows) < 2:
            return
        headers = [str(h) for h in rows[0]]
        col_title = None
        for i, h in enumerate(headers):
            if h == "title":
                col_title = i
                break
        if col_title is None:
            print("找不到 title 列")
            return
        for row in rows[1:]:
            title = str(row[col_title]) if col_title < len(row) and row[col_title] else ""
            if title:
                song = extract_song_name(title)
                print(song)
        return

    # 直接作为标题处理
    title = " ".join(sys.argv[1:])
    print(extract_song_name(title))


if __name__ == "__main__":
    main()
