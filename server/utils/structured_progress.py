import math


PREFIX = "PDF2ZH_PROGRESS:"


def progress_update(event):
    if event.get("type") == "error":
        raise RuntimeError(str(event.get("error", "Translation failed")))
    update = {"status": "running"}
    if event.get("stage"):
        update["message"] = str(event["stage"])
    if "overall_progress" in event:
        value = float(event["overall_progress"])
        if not math.isfinite(value) or value < 0 or value > 100:
            raise ValueError("Invalid translation progress")
        update["progress"] = min(99, int(value))
    if event.get("type") == "finish":
        update.update(progress=99, message="正在校验和整理输出文件")
    return update
