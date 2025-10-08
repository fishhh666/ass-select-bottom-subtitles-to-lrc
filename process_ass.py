import re
from pathlib import Path
import shutil

def get_playresy(text: str) -> int | None:
    """从 [Script Info] 段中提取 PlayResY 数字；若失败返回 None"""
    m = re.search(r"(?mi)^\s*PlayResY\s*:\s*(\d+)\s*$", text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None

def process_file(path: Path, dest_dir: Path) -> tuple[Path, bool, bool]:
    """
    删除规则：
      1. 含 '\move' 的行整行删除；
      2. 含 '\pos(x,y)' 且 y < PlayResY / 2 的行整行删除；
    若 PlayResY 缺失或非法，跳过文件。
    """
    text = path.read_text(encoding="utf-8-sig", errors="replace")

    # --- 读取 PlayResY ---
    m = re.search(r"(?mi)^\s*PlayResY\s*:\s*(\d+)\s*$", text)
    if not m:
        print(f"未更改: {path.name}（获取视频高度失败）")
        return path, False, False
    try:
        playresy = int(m.group(1))
    except ValueError:
        print(f"未更改: {path.name}（获取视频高度失败）")
        return path, False, False

    threshold = playresy / 2.0

    # --- 匹配规则 ---
    move_re = re.compile(r"\\move", re.IGNORECASE)
    pos_re = re.compile(r"\\pos\s*\(([\d.]+)\s*,\s*([\d.]+)\)", re.IGNORECASE)


    new_lines = []
    for line in text.splitlines(keepends=True):
        # 含 move → 删除
        if move_re.search(line):
            continue

        # 含 pos() → 判断第二个数字(y)是否小于阈值
        m = pos_re.search(line)
        if m:
            try:
                y = float(m.group(2))
                if y < threshold:
                    continue
            except ValueError:
                pass

        # 保留行
        new_lines.append(line)

    new_text = "".join(new_lines)
    dest_dir.mkdir(exist_ok=True)
    out_path = dest_dir / path.name
    out_path.write_text(new_text, encoding="utf-8", errors="replace")

    modified = (new_text != text)
    if not modified:
        print(f"未更改: {path.name}")
    return out_path, modified, True

# ----------------（ass to lrc）----------------

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
    minutes = int(total // 60)
    seconds = int(total % 60)
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
        parts = line.split(",", 9)
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
        j = i + 1
        while j < n and abs(entries[j][0] - entries[i][0]) < 1e-9:
            j += 1
        group_len = j - i
        if group_len == 1:
            total, ts, lyric = entries[i]
            new_entries.append((total, ts, lyric))
            i = j
            continue
        cur_total = entries[i][0]
        if j < n:
            next_total = entries[j][0]
            span = next_total - cur_total
            if span <= 1e-6:
                step = 0.05
                for k in range(group_len):
                    t = cur_total + step * k
                    ts_str = format_time_from_total(t)
                    new_entries.append((t, ts_str, entries[i + k][2]))
            else:
                step = span / group_len
                for k in range(group_len):
                    t = cur_total + step * k
                    ts_str = format_time_from_total(t)
                    new_entries.append((t, ts_str, entries[i + k][2]))
        else:
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
        replaced_file, modified, ok_to_continue = process_file(f, replaced_dir)
        # PlayResY 不合法则直接跳过所有后续
        if not ok_to_continue:
            continue
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
