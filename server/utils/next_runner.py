import asyncio
import json
import logging

from babeldoc.assets.assets import warmup
from pdf2zh_next.config import ConfigManager
from pdf2zh_next.high_level import do_translate_async_stream

from structured_progress import PREFIX


async def main():
    logging.basicConfig(level=logging.WARNING)
    settings = ConfigManager().initialize_config()
    files = list(settings.basic.input_files)
    if len(files) != 1:
        raise ValueError("Exactly one input PDF is required")
    settings.basic.input_files = set()
    warmup()
    finished = False
    async for event in do_translate_async_stream(settings, files[0]):
        # 仅传递进度字段，避免输出模型配置或翻译内容。
        payload = {key: event[key] for key in ("type", "stage", "overall_progress", "error") if key in event}
        print(PREFIX + json.dumps(payload, ensure_ascii=False), flush=True)
        if event.get("type") == "error":
            raise RuntimeError(str(event.get("error", "Translation failed")))
        finished = event.get("type") == "finish"
    if not finished:
        raise RuntimeError("Translation ended without a finish event")


if __name__ == "__main__":
    asyncio.run(main())
