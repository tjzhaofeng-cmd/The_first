"""Visible, bounded UI capture only; no network, cookies or private APIs."""
import argparse
import json
import sys
import time
from pathlib import Path
import yaml
from capture.screenshot_utils import CaptureStore, similarity


def select_region(gui):
    input("鼠标移到评论区域左上角，保持鼠标不动，用 Alt+Tab 切回终端按 Enter：")
    x1, y1 = gui.position()
    input("鼠标移到评论区域右下角，保持鼠标不动，用 Alt+Tab 切回终端按 Enter：")
    x2, y2 = gui.position()
    if x2 <= x1 or y2 <= y1:
        raise ValueError("区域必须从左上到右下选择")
    return [x1, y1, x2 - x1, y2 - y1]


def wait_or_pause(seconds):
    import msvcrt
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if msvcrt.kbhit():
            key = msvcrt.getwch().lower()
            if key == "q":
                raise KeyboardInterrupt
            if key == "p":
                input("已暂停。检查微信；若有验证/限制请按 Ctrl+C 停止。确认正常后 Enter 继续。")
                deadline = time.monotonic() + seconds
        time.sleep(0.1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default="data/screenshots/session01")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--mode", choices=["manual", "auto"], default="manual")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("本模块仅支持 Windows 桌面；云端请使用截图导入和处理模块")
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        print('无法设置 DPI 感知；请手工校验截图区域，必要时使用 100% 缩放。')
    import pyautogui as gui
    gui.FAILSAFE = True
    gui.PAUSE = 0.3
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))["capture"]
    limit = args.limit if args.limit is not None else config["max_screenshots"]
    if not 1 <= limit <= 50:
        parser.error("每批限 1–50 张，默认 10 张；先验证再续采")
    if config["delay_seconds"] < 3 or not -3 <= config["scroll_clicks"] <= -1:
        parser.error("自动操作间隔至少 3 秒，滚动幅度限 -1 至 -3")
    directory = Path(args.directory)
    path = directory / "manifest.json"
    if path.exists():
        region = json.loads(path.read_text(encoding="utf-8"))["region"]
        print("复用区域", region, "；请保持窗口位置、缩放和列表宽度不变。")
    else:
        region = select_region(gui)
    if not gui.onScreen(region[0], region[1]) or not gui.onScreen(
            region[0] + region[2] - 1, region[1] + region[3] - 1):
        parser.error("选择区域超出主屏幕；请将微信移至主屏幕重新选择")
    print("请确认有权采集，且平台允许。自动化不能保证不触发限制。")
    print("遇到验证码/异常登录/访问限制必须立即停止；本程序不处理验证。")
    print("自动模式终端 p 暂停，q 或 Ctrl+C 停止；鼠标移到屏幕角落触发 failsafe。")
    print("截图会保留原界面信息，仅本地保存，分享前应遮挡头像昵称。")
    if input("检查所选区域无无关内容，输入 START 开始本批：") != "START":
        return
    store = CaptureStore(directory, region)
    previous, unchanged, reason = None, 0, "batch_limit"
    try:
        for index in range(limit):
            if args.mode == "manual":
                command = input("手动滚动/展开全文后，Enter 截图；p 暂停，q 结束：").strip().lower()
                if command == "q":
                    reason = "user_stop"
                    break
                if command == "p":
                    input("已暂停；确认正常后 Enter 返回截图准备，Ctrl+C 停止。")
                    input("准备好截图后 Enter：")
            else:
                # Never scroll before the first frame of a new batch.
                wait_or_pause(config["delay_seconds"])
                if index:
                    gui.moveTo(region[0] + region[2] // 2, region[1] + region[3] // 2)
                    gui.scroll(config["scroll_clicks"])
                    wait_or_pause(config["delay_seconds"])
            image = gui.screenshot(region=tuple(region))
            if previous is not None and similarity(previous, image) >= config["unchanged_similarity"]:
                unchanged += 1
            else:
                unchanged = 0
            print("已保存", store.save(image))
            if args.mode == 'auto' and previous is not None and unchanged == 0:
                from processing.merge_reviews import estimate_shift
                displacement = estimate_shift(previous, image)
                if displacement is None or displacement > image.height * (1 - config.get('min_overlap_ratio', .3)):
                    answer = input('无法确认足够截图重叠，已暂停。检查是否漏采；q 停止，Enter 确认后继续：')
                    if answer.lower().strip() == 'q':
                        reason = 'overlap_unconfirmed'
                        break
            previous = image
            if unchanged >= config["unchanged_limit"]:
                reason = "unchanged"
                print("画面连续未变化：已停止。请人工检查是否到底、失焦或出现限制。")
                break
    except (KeyboardInterrupt, gui.FailSafeException):
        reason = "user_stop"
        print("已停止，已有截图和 manifest 已保留。")
    except Exception:
        reason = "error"
        raise
    finally:
        store.finish(reason)


if __name__ == "__main__":
    main()
