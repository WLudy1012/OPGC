#!/usr/bin/env python3
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product
import tkinter as tk
from tkinter import messagebox

BASE_POWER = 200.0
BASE_INTERVAL = 2


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
    a: int
    groups: list[tuple[int, BeltMode]]
    total_power: float
    overage: float

    @property
    def k(self) -> int:
        return len(self.groups)

    @property
    def splitters(self) -> int:
        return sum(ai * mode.splitter_count for ai, mode in self.groups)


def generate_modes(b: float, max_ti: int = 2000) -> list[BeltMode]:
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


def compositions(n: int):
    if n == 0:
        yield []
        return
    for first in range(1, n + 1):
        for rest in compositions(n - first):
            yield [first, *rest]


def find_best(b: float, z: float) -> Solution | None:
    need = z - BASE_POWER
    a_min = max(0, math.ceil(need / b))
    modes = generate_modes(b)

    def better(lhs: Solution | None, rhs: Solution) -> Solution:
        if lhs is None:
            return rhs
        key_l = (lhs.overage, lhs.a, lhs.k, lhs.splitters)
        key_r = (rhs.overage, rhs.a, rhs.k, rhs.splitters)
        return rhs if key_r < key_l else lhs

    a = a_min
    while a <= a_min + 12:
        best_for_a: Solution | None = None
        for comp in compositions(a):
            k = len(comp)
            for mode_choice in product(modes, repeat=k):
                total = BASE_POWER + sum(ai * m.per_gen for ai, m in zip(comp, mode_choice))
                if total + 1e-9 < z:
                    continue
                over = total - z
                groups = sorted(zip(comp, mode_choice), key=lambda x: (-x[0], x[1].Ti))
                cand = Solution(a=a, groups=groups, total_power=total, overage=over)
                best_for_a = better(best_for_a, cand)
        if best_for_a is not None:
            return best_for_a
        a += 1
    return None


def format_solution(b: float, z: float, sol: Solution | None) -> str:
    if sol is None:
        return "无解，需要增加发电机数。"

    lines = ["【最优方案】", f"b={int(b)}, Z={int(z)}", f"a={sol.a}", "分组详情："]
    for idx, (ai, mode) in enumerate(sol.groups, start=1):
        out = "b" if mode.full_power else f"{mode.per_gen:.2f}"
        lines.append(f"主带{idx}：供 {ai} 台，xi={mode.xi}，yi={mode.yi}，Ti={int(mode.Ti)}s，单台输出={out}")

    belt_sum = " + ".join(f"{ai}×{('b' if m.full_power else f'{m.per_gen:.2f}') }" for ai, m in sol.groups)
    lines.append(f"总功率：200 + {belt_sum} = {sol.total_power:.2f}")
    waste_rate = (sol.overage / z) * 100 if z else 0.0
    lines.append(f"超出：{sol.overage:.2f} (浪费率{waste_rate:.2f}%)")
    lines.append("搭建方法：")

    for idx, (_, mode) in enumerate(sol.groups, start=1):
        seq = ["二分器"] * mode.xi + ["三分器"] * mode.yi
        if seq:
            chain = "主带 → " + " → ".join(seq)
            lines.append(
                f"带{idx}：{chain}，从最后一个分流器的一个出口接发电机输入，未使用出口全部回流至电池源头或回该主带入口。"
            )
        else:
            lines.append(f"带{idx}：主带直连发电机输入（无分流器），其余不使用的分支不存在。")

    return "\n".join(lines)


def calculate_text(b_text: str, z_text: str) -> str:
    b = float(b_text)
    z = float(z_text)
    if b <= 0 or z <= 0:
        raise ValueError("b 和 Z 必须为正数。")
    return format_solution(b, z, find_best(b, z))


def launch_gui() -> None:
    root = tk.Tk()
    root.title("传送带电池供电计算器")
    root.geometry("900x700")

    frame = tk.Frame(root, padx=12, pady=12)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="b（电池功率/秒）:").grid(row=0, column=0, sticky="w")
    b_var = tk.StringVar(value="3200")
    tk.Entry(frame, textvariable=b_var, width=20).grid(row=0, column=1, sticky="w", padx=8)

    tk.Label(frame, text="Z（总需求功率/秒）:").grid(row=1, column=0, sticky="w")
    z_var = tk.StringVar(value="6000")
    tk.Entry(frame, textvariable=z_var, width=20).grid(row=1, column=1, sticky="w", padx=8)

    output = tk.Text(frame, wrap="word", height=32)
    output.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(12, 0))

    scrollbar = tk.Scrollbar(frame, command=output.yview)
    scrollbar.grid(row=3, column=3, sticky="ns", pady=(12, 0))
    output.configure(yscrollcommand=scrollbar.set)

    frame.grid_rowconfigure(3, weight=1)
    frame.grid_columnconfigure(2, weight=1)

    def on_calculate() -> None:
        try:
            result = calculate_text(b_var.get().strip(), z_var.get().strip())
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc))
            return

        output.delete("1.0", tk.END)
        output.insert(tk.END, result)

    tk.Button(frame, text="计算", command=on_calculate, width=12).grid(row=2, column=0, pady=(10, 0), sticky="w")
    tk.Button(frame, text="退出", command=root.destroy, width=12).grid(row=2, column=1, pady=(10, 0), sticky="w")

    on_calculate()
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
