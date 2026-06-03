"""
发送确认弹窗 — 作为子进程运行，不阻塞 bot 主循环。

向 stdout 输出 "send" 或 "pause"，bot 据此决定是否发送。
"""

import sys
import tkinter as tk
from tkinter import ttk


def main():
    if len(sys.argv) < 2:
        print("send")
        return

    chat_name = sys.argv[1]

    win = tk.Tk()
    win.title("Bot 即将发送消息")
    win.resizable(False, False)
    win.attributes("-topmost", True)

    result = ["send"]
    paused = False
    remaining = [5]
    done = False
    after_id = [None]

    def finish(r: str):
        nonlocal done
        if done:
            return
        done = True
        result[0] = r
        if after_id[0] is not None:
            win.after_cancel(after_id[0])
        win.destroy()

    def on_click(_event=None):
        nonlocal paused
        if paused:
            # 第二次点击 → 立即发送
            finish("send")
        else:
            # 第一次点击 → 挂起
            paused = True
            status_label.config(
                text="已挂起，再次点击立即发送",
                foreground="orange",
            )

    def tick():
        if done:
            return
        if paused:
            after_id[0] = win.after(500, tick)
            return
        remaining[0] -= 1
        if remaining[0] <= 0:
            finish("send")
        else:
            status_label.config(
                text=f"{remaining[0]} 秒后自动发送（点击挂起）",
                foreground="gray",
            )
            after_id[0] = win.after(1000, tick)

    # 窗口关闭 → 直接发送（不挂起）
    def on_close():
        if not done:
            finish("send")

    win.protocol("WM_DELETE_WINDOW", on_close)

    # ---- UI ----------------------------------------------------------
    frame = ttk.Frame(win, padding=16)
    frame.pack()

    ttk.Label(
        frame,
        text=f"即将回复: {chat_name}",
        font=("Microsoft YaHei", 11, "bold"),
    ).pack(pady=(0, 8))

    status_label = ttk.Label(
        frame,
        text=f"{remaining[0]} 秒后自动发送（点击挂起）",
        foreground="gray",
    )
    status_label.pack(pady=(0, 8))

    # 可点击区域提示
    click_area = ttk.Label(
        frame,
        text="💡 点击此处挂起 / 再次点击发送",
        foreground="gray",
        cursor="hand2",
    )
    click_area.pack(pady=(8, 0))
    click_area.bind("<Button-1>", on_click)

    # "不再提醒" 按钮（独立事件，不触发挂起）
    def mute_forever(_event=None):
        finish("mute")

    mute_btn = ttk.Button(
        frame, text="不再提醒，直接发送",
    )
    mute_btn.pack(pady=(4, 0))
    mute_btn.bind("<Button-1>", mute_forever)

    # ---- Center on screen --------------------------------------------
    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    after_id[0] = win.after(1000, tick)
    win.mainloop()

    print(result[0])


if __name__ == "__main__":
    main()
