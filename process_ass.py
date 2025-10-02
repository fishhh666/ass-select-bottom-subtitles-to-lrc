import re
from pathlib import Path
import shutil

# --- 来自 remove_moves.py ---
PATTERN = r"\n.*(?:move|,(?:0|[1-9]\d?|[1-4]\d{2}|5[0-3]\d|540)(?:\.\d+)?\)).*"

def process_file(path: Path, dest_dir: Path) -> tuple[Path, bool]:
    """
    将正则替换后的内容写入 dest_dir，返回写入的目标文件路径和是否发生修改的布尔值。
    仅在未发生修改时输出提示（"未更改"），修改时不输出单条提示。
    """
    # 使用 errors="replace" 以在遇到不可解码字节时用替代字符替换，避免异常终止
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    new_text = re.sub(PATTERN, "", text)
    dest_dir.mkdir(exist_ok=True)
    out_path = dest_dir / path.name
    out_path.write_text(new_text, encoding="utf-8", errors="replace")
    modified = (new_text != text)
    if not modified:
        print(f"未更改: {path.name}")
    return out_path, modified

# --- 来自 ass_to_lrc.py ---
TIME_RE = re.compile(r"(\d+):(\d{2}):(\d{2})\.(\d{1,2})")

def parse_ass_time(t: str):
    m = TIME_RE.match(t.strip())
    if not m:
        return None, None
    h, mm, ss, cs = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4).ljust(2, "0"))
    total = h * 3600 + mm * 60 + ss + cs / 100.0
    minutes = int(total // 60)
    seconds = int(total % 60)
    hundredths = int(round((total - int(total)) * 100))
    if hundredths >= 100:
        hundredths -= 100
        seconds += 1
    if seconds >= 60:
        seconds -= 60
        minutes += 1
    return f"{minutes:02d}:{seconds:02d}.{hundredths:02d}", total

def format_time_from_total(total: float) -> str:
    # 将秒数（float）格式化为 mm:ss.hh（百位为 hundredths）
    minutes = int(total // 60)
    seconds = int(total % 60)
    # 分离秒的小数部分以计算百位
    frac = total - (minutes * 60 + seconds)
    hundredths = int(round(frac * 100))
    if hundredths >= 100:
        hundredths -= 100
        seconds += 1
    if seconds >= 60:
        seconds -= 60
        minutes += 1
    return f"{minutes:02d}:{seconds:02d}.{hundredths:02d}"

def clean_ass_text(s: str) -> str:
    # 移除 ASS 覆盖标签，合并换行为一个空格
    s = re.sub(r"\{.*?\}", "", s)
    s = s.replace(r"\N", " ").replace(r"\n", " ")
    return s.strip()

def convert_file(path: Path, out_dir: Path) -> tuple[bool, str | None]:
    """
    将传入的（已替换后的）.ass 文件转换为 out_dir 目录下的 .lrc 文件。
    返回 (成功?, 原因或 None)。若返回 (False, "exists") 表示未转换因为 .lrc 已存在；
    若返回 (False, None) 表示未转换但不是因为已存在（主流程会打印通用提示）。
    """
    # 使用 errors="replace" 以在遇到不可解码字节时用替代字符替换，避免异常终止
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    entries = []
    for line in lines:
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)  # 文本在第9个逗号之后
        if len(parts) < 10:
            continue
        start = parts[1].strip()
        raw_text = parts[9].strip()
        timestamp, total = parse_ass_time(start)
        if timestamp is None:
            continue
        lyric = clean_ass_text(raw_text)
        if not lyric:
            continue
        entries.append((total, timestamp, lyric))

    if not entries:
        return False, "no_entries"

    entries.sort(key=lambda x: x[0])

    out_path = out_dir / (path.stem + ".lrc")
    if out_path.exists():
        print(f"{path.name}未转换（lrc已存在）")
        return False, "exists"

    # 将重复时间戳的连续组进行重分配
    new_entries = []
    i = 0
    n = len(entries)
    while i < n:
        # 查找从 i 开始的相同时间戳组（基于 total 值相等）
        j = i + 1
        while j < n and abs(entries[j][0] - entries[i][0]) < 1e-9:
            j += 1
        group_len = j - i
        if group_len == 1:
            # 单项，直接保留原时间戳
            total, ts, lyric = entries[i]
            new_entries.append((total, ts, lyric))
            i = j
            continue

        # group_len >= 2，需要重分配时间戳
        cur_total = entries[i][0]
        # 找下一不同时间点的 total
        if j < n:
            next_total = entries[j][0]
            span = next_total - cur_total
            # 若下一个时间点与当前相等或跨度极小，则退化为小步长分配
            if span <= 1e-6:
                step = 0.05  # fallback step 0.05s
                for k in range(group_len):
                    t = cur_total + step * k
                    ts_str = format_time_from_total(t)
                    new_entries.append((t, ts_str, entries[i + k][2]))
            else:
                # 在 cur_total 和 next_total 之间均匀生成 group_len 个时间点
                step = span / group_len
                for k in range(group_len):
                    t = cur_total + step * k
                    ts_str = format_time_from_total(t)
                    new_entries.append((t, ts_str, entries[i + k][2]))
        else:
            # 没有下一个时间点，向后使用固定小步长分配
            step = 0.05
            for k in range(group_len):
                t = cur_total + step * k
                ts_str = format_time_from_total(t)
                new_entries.append((t, ts_str, entries[i + k][2]))
        i = j

    # 确保按时间排序（重分配后顺序可能保持，但再次排序以保证）
    new_entries.sort(key=lambda x: x[0])

    out_lines = [f"[{ts}]{ly}" for _, ts, ly in new_entries]
    out_path.write_text("\n".join(out_lines), encoding="utf-8", errors="replace")
    return True, None

# --- 主流程：将替换后的 .ass 写入“替换后ass”，再用这些文件生成 .lrc（.lrc 写回原目录） ---
def main():
    p = Path(".")
    replaced_dir = p / "替换后ass"
    replaced_dir.mkdir(exist_ok=True)

    ass_files = list(p.glob("*.ass"))
    if not ass_files:
        print("未找到 .ass 文件")
        return

    total = len(ass_files)
    modified_count = 0
    converted_count = 0

    # 处理：将替换后的 .ass 写入 替换后ass，并用这些文件生成 .lrc（输出到原目录）
    for f in ass_files:
        replaced_file, modified = process_file(f, replaced_dir)  # 写入替换后ass，返回新路径和是否修改
        if modified:
            modified_count += 1
        converted, reason = convert_file(replaced_file, p)
        if converted:
            converted_count += 1
        else:
            # 若不是因为已有 .lrc 导致未转换，则打印通用提示 "XXX.ass未转换"
            if reason != "exists":
                print(f"{f.name}未转换")

    print(f"共{total}个ass文件，本次共成功修改{modified_count}个，成功转换{converted_count}个。")

if __name__ == "__main__":
    main()