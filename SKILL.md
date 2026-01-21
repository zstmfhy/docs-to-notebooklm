---
name: docs-to-notebooklm
description: 从技术文档网站批量抓取内容并同步到 Google NotebookLM。支持 VitePress、Docusaurus、GitBook、VuePress 等框架。功能包括：(1)提取文档导航链接，(2)下载页面并转换为 Markdown，(3)自动分批上传到 NotebookLM（每本 50 文件限制），(4)支持增量同步和断点续传。适用于需要将技术文档导入 NotebookLM 进行 AI 分析和检索的场景。
---

# Docs to NotebookLM

从各种技术文档网站批量抓取内容并同步到 Google NotebookLM 的工具集。

## 功能特性

- 🌐 **多框架支持**: VitePress, Docusaurus, GitBook, VuePress
- 🤖 **智能提取**: 自动识别文档结构，提取纯文本
- 📦 **自动分批**: NotebookLM 限制 50 文件/笔记本，自动创建多个
- 🔄 **增量同步**: 支持断点续传和进度保存
- 🎯 **精准抓取**: Playwright 处理动态加载页面

## 快速开始

### 安装依赖

```bash
pip install playwright beautifulsoup4 html2text
playwright install chromium
npm install -g @notebooklm/cli
notebooklm login
```

### 基本使用

```bash
# 1. 提取文档链接
python scripts/extract_sidebar_iterative.py "https://docs.example.com" \
    --output links.json --delay 1.5

# 2. 下载为 Markdown
python scripts/download_markdown.py --input links.json \
    --output docs/ --delay 2.0

# 3. 上传到 NotebookLM
python scripts/upload_markdown_to_notebooklm.py --input docs/ \
    --notebook "技术文档" --yes
```

## 脚本说明

### extract_sidebar_iterative.py

提取文档网站的导航链接。

```bash
python scripts/extract_sidebar_iterative.py <start_url> \
    --output links.json \
    --delay 1.5 \
    --max-pages 1000
```

**参数**:
- `start_url`: 文档网站起始 URL
- `--output`: 输出文件路径（JSON 格式）
- `--delay`: 页面加载延迟（秒），默认 1.0
- `--max-pages`: 最大抓取页面数，默认 1000
- `--headless`: 无头模式运行
- `--cookie`: 添加认证 cookie

**输出**:
- `links.json`: 所有文档链接
- `links.txt`: 文本格式链接列表
- `extract_progress.json`: 进度文件（支持断点续传）

### download_markdown.py

下载文档页面并转换为 Markdown。

```bash
python scripts/download_markdown.py \
    --input links.json \
    --output docs/ \
    --delay 2.0
```

**参数**:
- `--input`: 链接文件（JSON 或 TXT 格式）
- `--output`: 输出目录
- `--delay`: 请求延迟（秒），默认 1.5
- `--concurrent`: 并发数，默认 1
- `--max-files`: 最大下载数量

**输出**:
- `docs/`: Markdown 文件目录
- `README.md`: 生成的索引
- `download_progress.json`: 进度文件

### upload_markdown_to_notebooklm.py

上传 Markdown 文件到 NotebookLM。

```bash
python scripts/upload_markdown_to_notebooklm.py \
    --input docs/ \
    --notebook "我的文档" \
    --yes \
    --batch-size 50
```

**参数**:
- `--input`: 输入目录
- `--notebook`: 笔记本名称
- `--pattern`: 文件匹配模式，默认 `*.md`
- `--yes`: 跳过确认
- `--delay`: 上传延迟（秒），默认 0.5
- `--batch-size`: 每批文件数，最大 50

**特性**:
- 自动分批：超过 50 文件时创建多个笔记本
- 进度跟踪：每 10 个文件显示进度
- 错误处理：失败文件保存到 `_failed_uploads.txt`

## 使用示例

### 示例 1: 火山引擎 GPU 文档

```bash
# 提取链接
python scripts/extract_sidebar_iterative.py \
    "https://www.volcengine.com/docs/6419/70481?lang=zh" \
    --output volc_links.json

# 下载文档
python scripts/download_markdown.py \
    --input volc_links.json \
    --output volc_docs/ \
    --delay 2.0

# 上传（96 个文件 → 2 个笔记本）
python scripts/upload_markdown_to_notebooklm.py \
    --input volc_docs/ \
    --notebook "火山引擎GPU文档" \
    --yes
```

### 示例 2: 需要登录的文档

```bash
# 添加认证 cookie
python scripts/extract_sidebar_iterative.py \
    "https://docs.internal.com" \
    --output internal_links.json \
    --cookie "session_id=xxxxx"
```

### 示例 3: 大量文档（自动分批）

```bash
# 120 个文件会自动创建 3 个笔记本
python scripts/upload_markdown_to_notebooklm.py \
    --input large_docs/ \
    --notebook "大型文档集" \
    --batch-size 40 \
    --yes
```

## NotebookLM 限制处理

NotebookLM 每个笔记本最多 **50 个来源**。

**自动分批逻辑**:
```
96 个文件 ÷ 50 每批 = 2 个笔记本

笔记本 1: "大型文档集" (50 个文件)
笔记本 2: "大型文档集 (2)" (46 个文件)
```

## 常见问题

### Q: Playwright 浏览器未安装？

```bash
playwright install chromium
```

### Q: 提取不到链接？

移除 `--headless` 选项查看浏览器行为：

```bash
python scripts/extract_sidebar_iterative.py \
    "https://docs.example.com" \
    --output links.json
```

### Q: 上传失败？

- 检查登录状态: `notebooklm status`
- 减小延迟: `--delay 0.3`
- 查看失败文件: `_failed_uploads.txt`

### Q: 文件内容不完整？

增加延迟等待 JS 加载：

```bash
python scripts/extract_sidebar_iterative.py \
    "https://docs.example.com" \
    --output links.json \
    --delay 3.0
```

## 技术栈

- **Playwright**: 浏览器自动化，处理动态内容
- **BeautifulSoup**: HTML 解析和内容提取
- **html2text**: HTML 转 Markdown
- **NotebookLM CLI**: 与 Google NotebookLM 交互

## 依赖项

```
playwright>=1.40.0
beautifulsoup4>=4.12.0
html2text>=2020.1.16
```

## 最佳实践

1. **速率限制**: 使用合理的延迟（1-2 秒）避免被封
2. **批量处理**: 大量文档自动分批，无需手动干预
3. **进度保存**: 所有脚本支持断点续传
4. **错误处理**: 检查失败文件列表并重试

## 输出文件

### 链接提取
- `links.json`: JSON 格式链接
- `links.txt`: 纯文本链接
- `extract_progress.json`: 进度信息

### 下载
- `docs/*.md`: Markdown 文件
- `docs/README.md`: 索引文件
- `download_progress.json`: 下载进度

### 上传
- `.notebooklm_info.json`: 笔记本 ID
- `.upload_summary.json`: 上传摘要
- `_failed_uploads.txt`: 失败列表

## 许可证

MIT License
