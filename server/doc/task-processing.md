# 翻译进度与重复请求

Python 安装的 PDF2zh Next 通过 `do_translate_async_stream` 提供结构化进度。Server 使用 `overall_progress` 显示总体百分比，使用 `stage` 显示当前阶段。阶段计数和终端宽度不会影响百分比。引擎结束后，Server 校验 PDF、整理输出并保存结果，完成这些步骤后显示 100%。原生 PDF2zh 和独立 Windows 可执行文件保留原有进度来源；任务完成之前，Server 将进度限制在 99% 以内。

`/translate`、`/compare`、`/crop-compare` 使用 PDF 内容、输入类型、请求配置、配置模板摘要和操作名称生成 SHA-256 标识。文件改名不会触发重复工作。语言、模型、服务、输出选项或内容发生变化时创建新任务。

`config/jobs.sqlite3` 使用事务和唯一约束登记任务。重复请求在任务运行期间取得同一个 `taskId`；完成后，在输出文件存在且 SHA-256 校验一致时取得原结果。同步客户端等待共享任务结束，异步客户端继续查询任务进度。失败、服务重启时中断、输出缺失或被修改的任务允许再次执行。

每个任务使用 `translated/.jobs/<taskId>` 内的输入文件和独立配置，任务目录权限为 0700，配置权限为 0600（在支持这些权限的系统上）。输出校验完成后原子移动到公共目录，文件名以任务 UUID 开头，避免同名文献覆盖。登记信息仅保存请求摘要、结果路径及文件摘要。一个数据目录应由一个 Server 实例使用。

插件对同一结果的并发导入只执行一次。再次收到具有任务 UUID 文件名的结果时，检查目标文献下已有附件及本地文件，存在时直接复用；独立附件在同一文献库的顶层附件中检查。删除结果附件或本地文件后可以重新导入。

`ZOTERO_PDF2ZH_DATA` 可指定配置和输出的数据目录；默认使用 Server 所在目录。已有安装更新代码后才开始登记新的请求，更新前生成的文件不自动登记。

## 验证

安装 `server/requirements.txt` 后，在仓库根目录运行无需翻译 API 的回归测试：

```sh
PYTHONPATH=server:server/tests python -m unittest test_job_endpoints test_job_registry test_structured_progress test_task_progress test_download_filename_routing
```

这些测试使用真实 SQLite 并发事务、真实 PDF 合并和 Flask 请求，覆盖并发去重、完成结果复用、改名复用、同名内容隔离、异步文件发布、失败重试、重启恢复和完成前的进度限制。

安装 PDF2zh Next 2.9.0 及其依赖、完成模型资产初始化后，可以运行真实引擎集成测试：

```sh
PYTHONPATH=server python -m unittest discover -s server/integration
```

集成测试检查 BabelDOC 加权进度，并生成只有一句英文的测试 PDF，验证真实翻译、引擎进度事件和单语、双语输出。默认使用引擎内置的 SiliconFlow 免费服务，需要网络，无需付费 API 密钥。可以通过 `PDF2ZH_TEST_SERVICE=bing` 或 `PDF2ZH_TEST_SERVICE=google` 选择其他免费服务。测试临时目录位于仓库内并由 `.gitignore` 忽略。

插件检查在 `plugin` 目录执行 `npm test` 和 `npm run build`。
