#!/usr/bin/env python3
from __future__ import annotations

import math
import queue
import threading
from dataclasses import dataclass
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttkb
from ttkbootstrap.constants import BOTH, END, EW, LEFT, N, NSEW, W
from ttkbootstrap.scrolled import ScrolledText

BASE_GENERATION = 200.0
BASE_INTERVAL = 2
MAX_TI = 2000


@dataclass(frozen=True)
class BeltMode:
    xi: int
    yi: int
    Ti: float
    per_gen: float
    full_power: bool

    @property
    def splitter_count(self) -> int:
        return self.xi + self.yi


@dataclass
class Solution:
    e: int
    groups: list[tuple[int, BeltMode]]
    total_generation: float
    overage: float

    @property
    def k(self) -> int:
        return len(self.groups)

    @property
    def splitters(self) -> int:
        return sum(ai * mode.splitter_count for ai, mode in self.groups)


def generate_modes(b: float, max_ti: int = MAX_TI) -> list[BeltMode]:
    modes: dict[tuple[int, int], BeltMode] = {}
    for xi in range(0, 12):
        for yi in range(0, 12):
            ti = BASE_INTERVAL * (2**xi) * (3**yi)
            if ti > max_ti:
                continue
            if ti <= 40:
                per = float(b)
                full = True
            else:
                per = (40.0 * b) / ti
                full = False
            modes[(xi, yi)] = BeltMode(xi=xi, yi=yi, Ti=float(ti), per_gen=per, full_power=full)
    return list(modes.values())


def find_best(b: float, q: float, aim: float) -> Solution | None:
    exact_mode = aim <= 1e-9

    if q <= BASE_GENERATION:
        total_generation = BASE_GENERATION
        overage = total_generation - q
        if exact_mode or overage <= aim + 1e-9:
            return Solution(e=0, groups=[], total_generation=total_generation, overage=overage)
        return None

    scale = 100
    e_min = max(0, math.ceil((q - BASE_GENERATION) / b))
    modes = generate_modes(b)
    mode_power_i = [int(round(m.per_gen * scale)) for m in modes]
    min_mode_i = min(mode_power_i)
    initial_over_i = int(round(max(0.0, BASE_GENERATION + e_min * b - q) * scale))
    upper_i = int(round((q + aim) * scale)) if not exact_mode else int(round(q * scale)) + initial_over_i

    def better(lhs: Solution | None, rhs: Solution) -> Solution:
        if lhs is None:
            return rhs
        key_l = (lhs.overage, lhs.e, lhs.k, lhs.splitters)
        key_r = (rhs.overage, rhs.e, rhs.k, rhs.splitters)
        return rhs if key_r < key_l else lhs

    dp_layers: list[dict[int, tuple[int, int, int, int]]] = [{0: (0, 0, -1, -1)}]
    e = 0
    best_overall: Solution | None = None
    while True:
        effective_aim = best_overall.overage if exact_mode and best_overall is not None else aim
        if e > e_min and BASE_GENERATION + (e * min_mode_i / scale) > q + effective_aim + 1e-9:
            return best_overall if exact_mode else None
        e += 1
        prev = dp_layers[e - 1]
        cur: dict[int, tuple[int, int, int, int]] = {}
        if exact_mode and best_overall is not None:
            upper_i = int(round((q + best_overall.overage) * scale))
        limit_i = max(0, upper_i - int(round(BASE_GENERATION * scale)))

        for total_i, (splitters, mask, _pt, _mi) in prev.items():
            for idx, mode in enumerate(modes):
                nt = total_i + mode_power_i[idx]
                if nt > limit_i:
                    continue

                nmask = mask | (1 << idx)
                ns = splitters + mode.splitter_count
                cand = (ns, nmask, total_i, idx)

                old = cur.get(nt)
                if old is None:
                    cur[nt] = cand
                    continue

                cand_key = (nmask.bit_count(), ns)
                old_key = (old[1].bit_count(), old[0])
                if cand_key < old_key:
                    cur[nt] = cand

        dp_layers.append(cur)

        if e < e_min:
            continue

        best_for_e: Solution | None = None
        for total_i in cur.keys():
            total_generation = BASE_GENERATION + (total_i / scale)
            if total_generation + 1e-9 < q:
                continue
            if not exact_mode and total_generation - 1e-9 > q + aim:
                continue

            overage = total_generation - q

            counts: dict[int, int] = {}
            trace_total = total_i
            for layer in range(e, 0, -1):
                state = dp_layers[layer][trace_total]
                mode_idx = state[3]
                counts[mode_idx] = counts.get(mode_idx, 0) + 1
                trace_total = state[2]

            groups = sorted(((cnt, modes[i]) for i, cnt in counts.items()), key=lambda x: (-x[0], x[1].Ti))
            cand = Solution(e=e, groups=groups, total_generation=total_generation, overage=overage)
            best_for_e = better(best_for_e, cand)

        if best_for_e is not None:
            if exact_mode:
                best_overall = better(best_overall, best_for_e)
                if best_overall.overage <= 1e-9:
                    return best_overall
            else:
                return best_for_e


def format_number(value: float) -> str:
    return str(int(value)) if abs(value - round(value)) < 1e-9 else f"{value:.2f}"


def format_solution(b: float, q: float, aim: float, sol: Solution | None) -> str:
    if sol is None:
        return f"在当前参数下无法将浪费控制在{format_number(aim)}以内"

    lines = ["【方案】", f"b={format_number(b)}, Q={format_number(q)}", f"E={sol.e}", "分组："]
    if sol.e == 0:
        lines.append("无需主带，使用基地自带固定发电。")
        waste_rate = (sol.overage / q) * 100 if q else 0.0
        lines.append(f"总平均功率：{sol.total_generation:.2f}")
        lines.append(f"超出：{sol.overage:.2f}（浪费率约{waste_rate:.2f}%）")
        lines.append("搭建：")
        lines.append("无需搭建。")
        return "\n".join(lines)

    for idx, (ai, mode) in enumerate(sol.groups, start=1):
        status = "满功率" if mode.full_power else "间歇"
        per_text = format_number(b) if mode.full_power else f"{mode.per_gen:.2f}"
        lines.append(
            f"主带{idx}：供{ai}台，xi={mode.xi}，yi={mode.yi}，Ti={int(mode.Ti)}s, 单台输出={per_text}，{status}"
        )

    waste_rate = (sol.overage / q) * 100 if q else 0.0
    lines.append(f"总平均功率：{sol.total_generation:.2f}")
    lines.append(f"超出：{sol.overage:.2f}（浪费率约{waste_rate:.2f}%）")
    lines.append("搭建：")

    for idx, (_, mode) in enumerate(sol.groups, start=1):
        seq = ["二分器"] * mode.xi + ["三分器"] * mode.yi
        if seq:
            chain = "主带→" + "→".join(seq)
            lines.append(
                f"带{idx}：{chain}，从最后一个分流器的一个出口接出发电机，其余未用出口全部回流至电池源头或该主带入口。"
            )
        else:
            lines.append(f"带{idx}：主带直连发电机输入，无分流器。")

    return "\n".join(lines)


def calculate_text(b_text: str, q_text: str, aim_text: str = "100") -> str:
    b = float(b_text)
    q = float(q_text)
    aim = float(aim_text)
    if b <= 0 or q < 0 or aim < 0:
        raise ValueError("b 必须为正数，Q 和 aim 不能为负数。")
    return format_solution(b, q, aim, find_best(b, q, aim))


def launch_gui() -> None:
    root = ttkb.Window(themename="flatly")
    root.title("传送带电池供电计算器")
    root.geometry("1020x760")
    root.minsize(900, 620)

    container = ttkb.Frame(root, padding=16)
    container.pack(fill=BOTH, expand=True)
    container.columnconfigure(0, weight=1)
    container.rowconfigure(2, weight=1)

    header = ttkb.Frame(container, bootstyle="light", padding=14)
    header.grid(row=0, column=0, sticky=EW)
    header.columnconfigure(0, weight=1)
    ttkb.Label(
        header,
        text="传送带电池供电计算器",
        font=("Microsoft YaHei UI", 18, "bold"),
        bootstyle="primary",
    ).grid(row=0, column=0, sticky=W)
    ttkb.Label(
        header,
        text="输入 b、Q、aim，搜索满足平均功率窗口的最优供电方案",
        font=("Microsoft YaHei UI", 10),
        bootstyle="secondary",
    ).grid(row=1, column=0, sticky=W, pady=(4, 0))

    control = ttkb.Labelframe(container, text=" 参数设置 ", padding=12, bootstyle="info")
    control.grid(row=1, column=0, sticky=EW, pady=(12, 10))
    control.columnconfigure(1, weight=1)
    control.columnconfigure(3, weight=1)
    control.columnconfigure(5, weight=1)

    b_var = tk.StringVar(value="3200")
    q_var = tk.StringVar(value="6000")
    aim_var = tk.StringVar(value="100")
    ttkb.Label(control, text="b（单台发电功率/秒）").grid(row=0, column=0, sticky=W, padx=(0, 8))
    ttkb.Entry(control, textvariable=b_var, width=18, bootstyle="primary").grid(row=0, column=1, sticky=EW)
    ttkb.Label(control, text="Q（Quantity demanded / 总用电功率/秒）").grid(row=0, column=2, sticky=W, padx=(14, 8))
    ttkb.Entry(control, textvariable=q_var, width=18, bootstyle="primary").grid(row=0, column=3, sticky=EW)
    ttkb.Label(control, text="aim（最大允许浪费）").grid(row=0, column=4, sticky=W, padx=(14, 8))
    ttkb.Entry(control, textvariable=aim_var, width=18, bootstyle="primary").grid(row=0, column=5, sticky=EW)

    action_bar = ttkb.Frame(control)
    action_bar.grid(row=1, column=0, columnspan=6, sticky=EW, pady=(10, 0))
    action_bar.columnconfigure(4, weight=1)

    output_card = ttkb.Labelframe(container, text=" 计算结果 ", padding=10, bootstyle="primary")
    output_card.grid(row=2, column=0, sticky=NSEW)
    output_card.rowconfigure(0, weight=1)
    output_card.columnconfigure(0, weight=1)

    output = ScrolledText(output_card, autohide=True, padding=8, bootstyle="light-round", font=("Consolas", 11))
    output.grid(row=0, column=0, sticky=NSEW)

    progress = ttkb.Progressbar(action_bar, mode="indeterminate", bootstyle="info-striped")
    progress.pack(side=LEFT, padx=(12, 0), fill="x", expand=True)

    calc_btn: ttkb.Button
    clear_btn: ttkb.Button
    _result_q: queue.Queue[tuple[str, str]] = queue.Queue()
    _calculating = False

    def set_busy(busy: bool) -> None:
        nonlocal _calculating
        _calculating = busy
        if busy:
            calc_btn.configure(state="disabled")
            clear_btn.configure(state="disabled")
            progress.start(10)
        else:
            progress.stop()
            calc_btn.configure(state="normal")
            clear_btn.configure(state="normal")

    def worker_calculate(b_text: str, q_text: str, aim_text: str) -> None:
        try:
            result = calculate_text(b_text, q_text, aim_text)
            _result_q.put(("ok", result))
        except ValueError as exc:
            _result_q.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001
            _result_q.put(("error", f"计算失败：{exc}"))

    def poll_result() -> None:
        if not _calculating:
            return
        try:
            status, payload = _result_q.get_nowait()
        except queue.Empty:
            root.after(80, poll_result)
            return

        set_busy(False)
        if status == "ok":
            output.delete("1.0", END)
            output.insert(END, payload)
        else:
            messagebox.showerror("输入错误", payload)

    def on_calculate() -> None:
        if _calculating:
            return

        b_text = b_var.get().strip()
        q_text = q_var.get().strip()
        aim_text = aim_var.get().strip()
        set_busy(True)
        threading.Thread(target=worker_calculate, args=(b_text, q_text, aim_text), daemon=True).start()
        root.after(80, poll_result)

    def on_clear() -> None:
        output.delete("1.0", END)

    calc_btn = ttkb.Button(action_bar, text="计算", command=on_calculate, bootstyle="success", width=12)
    calc_btn.pack(side=LEFT)
    clear_btn = ttkb.Button(action_bar, text="清空结果", command=on_clear, bootstyle="secondary-outline", width=12)
    clear_btn.pack(side=LEFT, padx=8)
    ttkb.Button(action_bar, text="退出", command=root.destroy, bootstyle="danger-outline", width=12).pack(side=LEFT)

    root.mainloop()


if __name__ == "__main__":
    launch_gui()
