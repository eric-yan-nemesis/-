# 词境 · LexiScope

一个可以在本地运行的 CEFR C1/C2 英语词汇学习工具。粘贴英语文本，或导入 DOCX、PDF，在原文中查看词汇高亮及中文注释，再导出注释文档和词汇表。前端使用 HTML、CSS 和 JavaScript，后端使用 Python 与 FastAPI。

原始项目需求的完整中文翻译见 [需求说明](docs/需求说明.zh-CN.md)。

## 词汇等级代表什么

本项目使用 Open Language Profiles 发布的 **Octanove Vocabulary Profile C1/C2 v1.0** 作为开放词汇等级参考。原始数据有 2,136 行，去除完全重复记录后有 2,108 条，涉及 1,955 个不同词头。该数据以 CC BY-SA 4.0 授权，固定于提交 `d4e45b75b38f27b30dfc5c44d8c571aec7e7092f`。出处、校验值及授权说明见 [data/SOURCES.md](data/SOURCES.md)。

这是开放词汇分级资料，不是 Cambridge English Vocabulary Profile，也不代表 CEFR 官方对当前句子中每个词义的认证。词条的词性、词义提示和句子上下文都可能影响结果。界面将参考来源支持的等级与估计等级分开，并对不确定的上下文匹配作提示；模型提出的新等级只能标为估计。

多词性或多等级词条会保留 `source_candidates` 和 `level_candidates`，例如 `brief` 的动词 C1 与法律名词 C2 在离线模式下仍是待消歧候选。AI 可以根据判断的词性选择已有来源记录的等级，不能凭空生成“来源支持”的新等级；词性不匹配或义项不符时，仍保留不确定性或降为估计。即使提供了 AI 注释，当前实现也不将语境标为已经人工核实。

离线模式不需要 API 密钥。它可以进行词汇匹配、高亮、词形归并和导出；部分常用词提供人工编写的中文释义、英文释义和例句。没有适合的离线注释时会提示需要结合上下文确认，而不会编造已核实的含义。开启 AI 后，后端可调用兼容的语言模型 API 辅助生成上下文注释。AI 输出仍可能出错，适合学习辅助，不适合作为考试分级或语言测评的唯一依据。

## 安装和启动

使用 Python 3.12 或更新版本。锁定依赖已在 Python 3.12 中安装检查；其中 `numpy==2.5.4` 要求 Python 3.12 及以上。以下命令从仓库根目录执行：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Windows PowerShell 激活虚拟环境的命令为 `.venv\Scripts\Activate.ps1`。启动后，在本地浏览器打开 `http://127.0.0.1:8000`。云环境使用已配置的访问方式；本项目的安装和健康检查不依赖公开网页预览。

`requirements.lock` 固定本次验证使用的完整依赖版本，`requirements.txt` 列出直接依赖。当前云环境已在 `/workspace/.venvs/lexiscope` 准备独立虚拟环境，可用 `source /workspace/.venvs/lexiscope/bin/activate` 激活；未来任务使用现有隔离的检出目录，无需另建 Git worktree。

检查后端是否可用：

```bash
curl --fail http://127.0.0.1:8000/api/health
```

默认不启动任何外部服务。API 密钥未配置时，使用词库模式即可完成基本工作流。

## 配置 AI 注释

以下变量只由后端读取：

| 变量 | 用途 | 默认值 |
| --- | --- | --- |
| `AI_API_KEY` | 模型服务密钥，属于秘密信息 | 未设置，禁用 AI |
| `AI_BASE_URL` | 兼容 OpenAI 的 API 根地址 | `https://api.openai.com/v1` |
| `AI_MODEL` | 注释模型名称 | `gpt-4.1-mini` |

在运行环境的安全配置中设置密钥；不要写入网页、JavaScript、版本库或示例文档。使用其他提供商时，先确认其 API 兼容性、数据政策和网络访问权限。

用户在界面中明确开启 AI 后，待分析文本才会发送到配置的模型服务。不要对无法向该服务披露的敏感文档启用 AI。密钥存在不代表服务一定可访问，实际调用仍可能受模型权限、配额或网络策略影响。没有真实凭据时，自动化测试使用模拟响应，不等同于验证真实提供商可用。

AI 单次最多处理 16,000 个字符和 80 处已匹配词汇，最多补充 25 个新词或短语估计。超过处理限制或服务调用失败时返回离线结果及提示。当前环境未配置真实 API 密钥，尚未验证实际提供商调用；离线流程不受此限制影响。

## 文档处理与导出

- **输入：**粘贴文本、DOCX 和 PDF。上传文件最大 10 MiB，提取文本最大 100,000 个字符，PDF 最大 100 页。
- **DOCX：**使用 `python-docx` 提取段落和表格内容，同时检查归档结构和解压大小。
- **PDF：**使用 PyMuPDF 提取可选择的文字。扫描件可按需开启英文 OCR；OCR 需要另行安装 Tesseract 及英文语言数据。
- **输出：**带高亮和词汇表的 DOCX、PDF，以及使用 UTF-8 BOM 编码的 CSV 词汇清单。词汇表保留等级、词性、中文含义、英文释义、例句、出现次数和来源信息。

导出文件根据提取的文本重新排版，保留段落层次，并添加注释。它不保证恢复原始 DOCX/PDF 的字体、页眉页脚、图片、分栏、分页位置或表格几何布局。复杂 PDF 的阅读顺序和 OCR 识别可能存在误差，分析前应检查提取结果。

### 可选 OCR

在 Debian/Ubuntu 上，可通过系统包管理器安装 OCR 工具：

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

部分系统还需要设置 `TESSDATA_PREFIX`，使 PyMuPDF 能定位 Tesseract 的语言数据目录。OCR 只在用户选择后、且页面缺少可用文字时执行；本身不需要模型 API。

## 架构

```text
浏览器：粘贴或上传 → 显示高亮、词汇表和来源 → 下载导出文件
                 ↓ 同源 HTTP API
FastAPI：校验和限制 → 文本提取 → 词形/短语匹配 → 上下文注释
                 ↓                              ↓ 可选
        python-docx / PyMuPDF              模型提供商 API
                 ↓
        内存生成 DOCX / PDF / CSV
```

前端通过文本节点渲染用户内容，不把原文或模型输出当作 HTML。后端负责文件解析、词汇资料、API 凭据和导出。匹配记录保存原文的字符位置，因此高亮可保留用户输入的大小写、词形和重复出现的位置；同一词汇可以在词汇表中归并计数。短语需要避免与其内部的单词重复高亮。词形归并是受限的规则匹配，不能替代完整的词性标注或词义消歧。

词形变化使用 `lemminflect` 并受来源词性约束；多词条目按最长匹配优先处理。AI 可将同一词在不同语境中的注释分开，但自动判断仍需核对。

主要接口：

| 接口 | 用途 |
| --- | --- |
| `GET /api/health` | 健康状态、AI 配置和 OCR 能力 |
| `POST /api/analyze` | 接收 `text`、`use_ai`、`include_estimates`，返回词汇、出现位置和提示 |
| `POST /api/documents` | 接收 multipart 文件及 `ocr` 选项，返回提取文本和提示 |
| `POST /api/export/docx` | 从分析结果生成 DOCX |
| `POST /api/export/pdf` | 从分析结果生成 PDF |
| `POST /api/export/csv` | 从分析结果生成 CSV |

分析示例：

```bash
curl --fail http://127.0.0.1:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text":"The meticulous researcher alleviated pressure and remained resilient.","use_ai":false,"include_estimates":true}'
```

## 测试

从仓库根目录运行：

```bash
python -m pytest -q
```

测试包含词汇来源和等级约束、常见词形与重复词匹配、上下文不确定性、API 输入限制、DOCX/PDF 文本提取、段落与高亮保留、实际导出文件解析、中文文本，以及 CSV 公式注入防护。自动化测试中的固定样例用于验证这些行为，不构成完整的 CEFR 准确率评测。真实模型调用和 OCR 工具依赖运行环境，需与不依赖外部服务的测试结果分别看待。

## 安全和使用范围

文档在请求期间处理，不主动保留上传文件或分析结果。文件类型、大小、DOCX 解压大小和 PDF 页数受到限制；损坏、不支持或加密的输入会返回错误。CSV 导出对可能被电子表格作为公式执行的内容进行转义。

这是面向个人使用的原型。公开部署前，应添加身份认证、请求速率与并发限制、HTTPS、反向代理的请求大小限制、解析任务隔离及适合业务的数据保留政策。文档解析依赖应持续更新。服务日志和模型提供商可能有自己的保留政策，本项目的内存处理并不改变这些政策。

英文词汇和多词表达的覆盖受参考词库限制；未匹配到的词不等于低于 C1。不同来源可能对同一个词给出不同分级，特别是不同词性和义项。请保留界面和导出中的来源及不确定性说明。

第三方依赖的授权与词汇数据授权分别适用。PyMuPDF 采用 GNU Affero GPL v3（AGPL）或 Artifex 商业授权的双重许可；发布、提供网络服务或采用闭源分发方式时，应按实际使用方式满足适用许可，必要时取得商业授权。词汇数据及其改编仍按 CC BY-SA 4.0 保留署名、来源、授权链接和修改说明。
