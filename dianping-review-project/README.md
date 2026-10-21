# 同济联合广场 · 大众点评微信小程序评论研究工具

这是一个 **Windows 本地截图 → 本地/云端 OCR → 可复核整理 → 人工校对 → CSV/Excel** 的 Python 项目。云端不能读取、控制你的微信；本项目未采集真实评论，合成演示数据不得用于研究统计。首次只采集 **10 张截图**，核对效果后再决定是否继续。

## 当前交付与验证边界

- A：Windows 主屏幕区域选择、手动截图、有限自动滚动、暂停/停止、批次 manifest、断点续采及防覆盖代码已实现。云端没有 Windows 微信，实际操作尚未验证。
- B：PaddleOCR 3 CPU 适配、日期解析、评论候选分割、橙/灰/半星检测及来源坐标已实现。真实界面布局及 OCR 精度未验证。云端已安装 PaddleOCR，但官方模型下载被网络限制，未执行真实模型推理。
- C：有视觉重叠证据的跨屏合并、疑似重复标记、可追溯人工修改/合并、CSV/Excel/待核对表和 Streamlit 校对工具已实现，使用明确标记的合成图片和模拟 OCR 输入验证。
- 默认 `layout_verified: false`：所有自动候选进入核对流程。候选数不等于真实评论数；未拼接片段不计入正式评论表；未经人工确认，不应作为最终研究数据。

完整测试范围、结果及剩余限制见 [TEST_REPORT.md](TEST_REPORT.md)。

## 安全、隐私与访问边界

只在你有权访问、保存及分析，且平台允许的前提下使用。程序没有评论网络接口请求，不读取微信 Cookie/Token/签名，不处理或绕过验证码，也没有代理池、IP 轮换等功能。OCR 在本机计算；首次安装和模型下载需要网络，截图不发送给 OCR 服务。

自动模式每次滚轮仅 -1～-3 格，操作间隔至少 3 秒，默认 5 秒；这**不保证不会触发平台限制**。出现验证码、异常登录或访问限制时必须人工立即停止，不要继续自动操作。程序不能可靠自动识别所有验证页面。若平台不允许自动化，只使用手动截图或导入你手动保存的截图。

最终数据结构不包含昵称、头像、用户主页。原始截图仍可能含这些信息，仅限本地证据使用；默认忽略整个数据目录，切勿将原始截图上传公开仓库。首次检查头部/底部安全边距是否排除了昵称、会员等级及评论图片文字；布局算法无法在无真实样本的情况下保证绝不混入无关文字，分享/研究前必须逐条复核。上传云端样本前遮挡头像、昵称、主页入口等无关信息，保留日期、星星、正文和屏幕重叠区域。

## Windows 安装（推荐 Python 3.11，64 位）

1. 安装 Python 3.11，勾选 Python Launcher。打开命令提示符，运行 `py -3.11 --version` 验证。
2. 下载或克隆仓库，进入本项目目录 **`dianping-review-project`**。
3. 双击或在终端执行：

```bat
scripts\install_windows.bat
```

这会创建 `.venv`，安装基础处理、测试、PyAutoGUI 和校对界面依赖。OCR 额外安装：

```bat
.venv\Scripts\python.exe -m pip install -r requirements-ocr.txt
.venv\Scripts\python.exe -m pip check
```

默认 CPU，不需要 CUDA。若使用 Python 3.12，请手动 `py -3.12 -m venv .venv` 后执行同样的 pip 安装命令。不要在同一环境混装多个不同版本 OpenCV 包；本项目采用 PaddleOCR 兼容的 `opencv-contrib-python==4.10.0.84`。

第一次运行 OCR 要下载官方的 `PP-OCRv5_mobile_det` 与 `PP-OCRv5_mobile_rec` 模型。需要能访问官方模型来源，例如 `paddle-model-ecology.bj.bcebos.com`（官方 BOS 源），或 Paddle 支持的其他模型托管源。可在启动前选择官方源：

```bat
set PADDLE_PDX_MODEL_SOURCE=bos
```

不要关闭 TLS/校验。离线时，可以从可信官方来源准备相同模型的解压目录，在 `config.yaml` 的 `processing.ocr.text_detection_model_dir` 和 `text_recognition_model_dir` 中填写路径；目录应包含官方完整推理文件。路径建议使用正斜线，例如 `C:/models/PP-OCRv5_mobile_det`。尚未用真实本地模型包验证这一配置，应先运行少量截图确认。

## 第一步：采集 10 张截图

将微信放在**主屏幕**，固定窗口大小、位置、缩放和评论区域，打开“同济联合广场”地点本身的评价列表。终端窗口放在截图区域之外。不要同时运行两个采集实例，也不要改变窗口几何后复用旧会话。

### 推荐：手动滚动模式

```bat
scripts\run_capture.bat
```

- 按提示把鼠标移到评论列表左上、右下角。**保持鼠标位置，用键盘 Alt+Tab 切回终端按 Enter**，不要用鼠标点击终端，否则位置会变。
- 避开无关微信界面，但保留完整正文宽度及星星、日期；保持每张截图相同区域。
- 确认后输入 `START`。用鼠标手动滚动、按需手动展开全文，再回终端按 Enter 截图。程序不会自动点击“展开全文”。
- 每次滚动尽量保留 **30%～50%** 的前一屏内容；滚动格数不等于固定像素，必须检查重叠。
- `p` 暂停，`q` 或 `Ctrl+C` 停止。默认每批最多 10 张。
- 再次运行同一命令会按 manifest 续采，使用新批次编号和唯一文件名，不覆盖旧图。

自定义会话与批次上限：

```bat
scripts\run_capture.bat --directory data\screenshots\session02 --mode manual --limit 10
```

### 可选：有限自动滚动

仅当平台允许自动化，且你已经验证截图区域和滚动幅度：

```bat
scripts\run_capture.bat --mode auto --limit 10
```

终端拥有焦点时，按 `p` 暂停，按 `q` 或 `Ctrl+C` 停止；将鼠标移到主屏幕角落也可触发 PyAutoGUI failsafe。键盘控制不是全局热键，微信拥有键盘焦点时应先 Alt+Tab 切回终端，或使用鼠标角落停止。不要无人值守运行。

每批第一张不滚动，续采允许重复一帧，后续处理会保留来源。画面连续 3 次未变化时停止并提示；不能确认足够视觉重叠时会暂停，要求人工检查。它不能判断“所有可访问评价”已经采完，也不能保证列表加载完整。最后一条评论可能仍被屏幕裁切，必须人工核对。

### 仅使用手动保存的截图

不使用 PyAutoGUI 也可以。将已裁好、尺寸相同的截图按顺序命名为 `001.png`、`002.png` 等，放在单独目录：

```bat
.venv\Scripts\python.exe -m scripts.import_screenshots --source C:\my_screenshots --session data\screenshots\manual01
```

按文件名排序导入，原图不修改；重复导入同一文件内容会跳过。导入文件的 mtime 仅为文件时间，**不能保证是原始采集时间**，manifest 会标注 `time_source`。多次导入请按真实时间先后进行，不要把新补的早期截图追加到已有会话末尾；重新排序时建立新会话。

### 文件与恢复

会话目录保存 `capture_*.png` 与 `manifest.json`。每帧记录文件名、UTC 采集时间、批次、顺序、SHA-256；每次保存原子更新 manifest。截图落盘后进程异常终止，已完成的孤立 PNG 会在下次启动时恢复，标为 `recovered`，时间使用文件 mtime。未完成的 `.png.tmp` 不会被当作截图。截图丢失、校验和变化或区域变化会拒绝续采；不要直接删除 manifest 里的证据文件。

## 第二步：OCR 与结构化处理

默认会话：

```bat
scripts\run_processing.bat
```

指定会话与工作目录：

```bat
scripts\run_processing.bat data\screenshots\manual01 data\intermediate\manual01
```

等价的可独立运行命令：

```bat
.venv\Scripts\python.exe -m processing.pipeline process --session data\screenshots\session01 --work data\intermediate\session01
.venv\Scripts\python.exe -m processing.pipeline export --work data\intermediate\session01 --output data\output\session01
```

每张图片处理后保存检查点；中断后使用同一命令续跑。图片 SHA、配置、处理代码或 OCR 包版本变化时，受影响缓存会失效。原始未筛选 OCR 行不落盘，避免保存头部昵称等无关字段。中间 `reviews.json` 保存经过筛选的正文、日期、评分与截图坐标。请不要手改缓存，也不要把示例 OCR 输入当作真实识别结果。

`config.yaml` 是初始配置，布局参数**不是实测的大众点评固定值**：

- `header_gap`：日期与星星配对的最大垂直距离。
- `header_guard`：下一条头部和屏幕底部安全边距，默认 64 像素，减少昵称混入；会有意保留待补全文本。
- `rating.min_star_size/max_star_size`：星星大小范围；不同缩放需要校准。
- `photo_boxes`：明确的评论图片排除框 `[x, y, width, height]`，相对每张截图；列表滚动后图片位置会变化，不要在整批中盲目复用固定框。
- `layout_verified`：默认 false；仅在真实样本逐条对照通过后考虑改为 true，仍不能免除低置信度/缺失信息的核对。

### 识别与合并原则

- 无年份日期原样保留，标准日期留空；不会按当前年份或采集年份补年份。无效日期、相对日期进入核对。
- 星形轮廓、五颗排列、橙/灰面积及颜色顺序联合判断评分。模糊、未知颜色/轮廓、非五颗或填充不明确时评分为空；不能仅凭橙色像素量猜分。
- 日期、星星和空间布局共同生成评论候选。只发现日期时边界不确定；没有可信头部的画面只保存证据片段占位，不把整屏文字当评论。
- 自动照片区域检测是启发式，可能漏掉图片文字，或误排正文；被排除时有质量标记。真实图片布局需要样本校准。
- 跨屏合并需要连续截图的视觉重叠、位置对应及包含/足够长的文本首尾重叠共同支持。不能对齐、OCR 冲突或拼接不确定时保留原候选，进入核对，不猜正文。
- 同日期不作为同一条评论的依据。非几何确认的相似记录只标为疑似重复，不自动删除；同一天相同短句也可能来自不同用户。
- 折叠提示或底部裁切标记为 `incomplete`。末屏无后续头部时不会凭空认定最后一条完整。
- `ocr_confidence` 是 PaddleOCR 输出的最小相关行分数，非评论正确率；星级置信度和证据框另存在中间记录。

## 第三步：人工校对与最终导出

```bat
scripts\run_review.bat
```

Streamlit 仅绑定本机 `127.0.0.1`，在**你的 Windows 本地浏览器**打开终端显示的地址。不要绑定公共网卡或对外开放含截图的服务。

1. 左侧输入工作目录，如 `data/intermediate/session01`；选择评论或未拼接片段。
2. 查看原图（红框为候选、蓝框为正文行）、全部来源证据、文字、日期、评分、质量标记。
3. 修改正文并排除昵称、等级、日期说明词和照片中的文字；确认日期无年份时不要补。
4. 评分允许空值及 0～5 的半星。选择 `complete/incomplete/needs_review`，逐项确认后勾选“已逐项人工核对”。
5. 确认重复才勾选“从正式导出排除”，并选择对应记录；疑似重复默认保留。
6. 跨屏未合并时，在主记录中手动拼好正文，选择要并入的片段，取消主记录的“仍为未拼接片段”；保存后会保留全部来源，子片段从正式表排除。仅支持合并到一个主记录，不支持链式合并。
7. 点击“保存校对”，再点“应用校对并导出”。界面提供三个文件的下载按钮。

修改单独保存在 `corrections.json`，包含修改历史，不覆盖原始提取结果。OCR 结果变化使旧校对失效时会标 `correction_stale`，必须重新核对；不要直接把旧校对强行应用于新证据。同一时间只打开一个校对编辑会话；保存有文件锁，但多个浏览器可能显示旧值。

导出的三个文件：

- `同济联合广场_大众点评评论.xlsx`
- `同济联合广场_大众点评评论.csv`（UTF-8 BOM，便于 Excel 打开）
- `同济联合广场_待人工核对.xlsx`

主表恰好包含 `review_id, rating, review_date_raw, review_date_normalized, review_text, source_images, ocr_confidence, review_status, collected_at`。`source_images` 为 JSON 字符串数组。质量表额外保留 flags、疑似重复指向、排除/片段状态和证据坐标；未拼接片段只出现在质量表，不冒充独立评论。

未经人工核对的候选仍可在主表中带状态导出，**不能把主表行数当作最终有效评价数**。评分/日期/正文不确定、重复、拼接及布局问题都进入质量表。校对后重新导出才是最终数据。为避免 Excel/CSV 公式注入，CSV 中以 `= + - @` 开头的文字加一个前导单引号；JSON 原文不改，Excel 单元格按文本保存。

## 云端可复现演示（不访问微信、不依赖 OCR 模型）

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-ui.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m scripts.make_demo --directory data/demo
.venv/bin/python -m processing.pipeline process --session data/demo/screenshots --work data/demo/work --fixture data/demo/ocr_fixture.json
.venv/bin/python -m processing.pipeline export --work data/demo/work --output data/demo/output
```

Windows 将 `.venv/bin/python` 替换为 `.venv\Scripts\python.exe`。`--fixture` 明确跳过 OCR 推理，只测试布局/整理链路，所有导出文件加 `演示_非真实数据_` 前缀。不要将这类测试解释为真实 OCR 精度。演示目录已存在时生成器拒绝覆盖；可以换新目录。所有图像均由代码生成，带“合成样例”说明。

## 需要真实样本验证的项目

请先在本地采集 10 张并逐张检查。为校准，需要经遮挡昵称/头像的样本覆盖：同日多条评论、橙灰/半星、较短/跨两三屏的长正文、折叠提示、含照片的评论、滚动重叠、首/末屏和不同日期格式。保留原截图尺寸和 manifest 顺序；不要只提供裁掉上下文的单行文字。

尚不能保证：星级皮肤/缩放通用、照片文字完全排除、所有评论边界准确、OCR 无错字、所有跨屏片段可自动拼接、自动点击展开、自动识别验证码、自动判断已采完全部可访问评价。第一次应将程序输出与人工逐条对照，调整参数并复测，再扩大批次。

## 目录

```text
capture/          Windows 截图、原子存储与续采
processing/       OCR、日期、星级、候选分割、合并、去重、校对存储和 CLI
review_ui/        Streamlit 本地人工校对
export/           CSV、Excel、质量表
scripts/          Windows 启动、手动截图导入、合成样例生成
samples/          样本规范（真实样本不要提交）
tests/            可复现的合成/单元/集成/UI 测试
data/             本地截图、检查点及输出（Git 忽略）
```
