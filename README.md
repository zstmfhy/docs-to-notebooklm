# Docs to NotebookLM

> 📚 从各种技术文档网站批量抓取内容并同步到 Google NotebookLM 的工具集

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ 特性

- 🌐 **支持多种文档框架**: VitePress, Docusaurus, GitBook, VuePress 等
- 🤖 **智能内容提取**: 自动识别文档结构，提取纯文本内容
- 📦 **自动分批处理**: NotebookLM 每个知识库限制 50 个文件，自动创建多个笔记本
- 🔄 **增量同步**: 支持断点续传和进度保存
- 🎯 **精准抓取**: 使用 Playwright 处理动态加载的页面

## 🚀 快速开始

### 安装依赖

```bash
# 安装 Python 依赖
pip install playwright beautifulsoup4 html2text

# 安装 Playwright 浏览器
playwright install chromium
```

### 安装 NotebookLM CLI

```bash
npm install -g @notebooklm/cli
```

登录 NotebookLM:
```bash
notebooklm login
```

## 📖 使用方法

### 方法一：一键同步（推荐）

适用于简单的文档网站：

```bash
# 1. 提取文档链接
python scripts/extract_sidebar_iterative.py \
    "https://docs.example.com" \
    --output links.json \
    --delay 1.5

# 2. 下载为 Markdown
python scripts/download_markdown.py \
    --input links.json \
    --output docs/ \
    --delay 2.0

# 3. 上传到 NotebookLM
python scripts/upload_markdown_to_notebooklm.py \
    --input docs/ \
    --notebook "技术文档" \
    --yes
```

### 方法二：分步执行

#### 1. 提取文档链接

```bash
python scripts/extract_sidebar_iterative.py \
    "https://www.volcengine.com/docs/6419/70481" \
    --output volc_links.json \
    --delay 1.5 \
    --max-pages 200
```

**参数说明**:
- `--delay`: 页面加载延迟（秒），默认 1.0
- `--max-pages`: 最大抓取页面数，默认 1000
- `--headless`: 无头模式运行浏览器
- `--cookie`: 添加认证 cookie（适用于需要登录的网站）

#### 2. 下载文档内容

```bash
python scripts/download_markdown.py \
    --input volc_links.json \
    --output volc_docs/ \
    --delay 2.0 \
    --concurrent 1
```

**参数说明**:
- `--input`: 链接文件（支持 JSON 和 TXT 格式）
- `--output`: 输出目录
- `--delay`: 请求延迟（秒）
- `--concurrent`: 并发数（建议为 1，避免被封）

#### 3. 上传到 NotebookLM

```bash
python scripts/upload_markdown_to_notebooklm.py \
    --input volc_docs/ \
    --notebook "火山引擎GPU文档" \
    --yes \
    --delay 0.5 \
    --batch-size 50
```

**参数说明**:
- `--notebook`: 笔记本名称（超过 50 个文件时自动添加序号）
- `--yes`: 自动确认，跳过提示
- `--delay`: 上传延迟（秒）
- `--batch-size`: 每个笔记本的文件数（最大 50）

## 📁 项目结构

```
docs-to-notebooklm/
├── README.md                          # 本文件
├── SKILL.md                           # Claude Code 技能定义
└── scripts/
    ├── extract_sidebar_iterative.py   # 提取文档导航链接
    ├── download_markdown.py            # 下载文档为 Markdown
    └── upload_markdown_to_notebooklm.py # 上传到 NotebookLM
```

## 🎯 使用场景

### 场景 1: 同步火山引擎 GPU 文档

```bash
# 提取链接
python scripts/extract_sidebar_iterative.py \
    "https://www.volcengine.com/docs/6419/70481?lang=zh" \
    --output volc_gpu_links.json

# 下载文档
python scripts/download_markdown.py \
    --input volc_gpu_links.json \
    --output volc_gpu_docs/

# 上传到 NotebookLM（自动创建 2 个笔记本）
python scripts/upload_markdown_to_notebooklm.py \
    --input volc_gpu_docs/ \
    --notebook "火山引擎GPU云服务器文档" \
    --yes
```

### 场景 2: 同步需要登录的文档

```bash
# 添加认证 cookie
python scripts/extract_sidebar_iterative.py \
    "https://docs.internal.com" \
    --output internal_links.json \
    --cookie "session_id=xxxxx"
```

### 场景 3: 处理大量文档

```bash
# 使用较小的批次大小（每本 40 个文件）
python scripts/upload_markdown_to_notebooklm.py \
    --input large_docs/ \
    --notebook "大型文档集" \
    --batch-size 40 \
    --yes
```

## ⚙️ 高级配置

### NotebookLM 限制

NotebookLM 每个笔记本最多支持 **50 个来源**。本工具会自动：
- 计算需要的笔记本数量
- 创建多个笔记本并添加序号后缀
- 跟踪每个笔记本的上传进度

示例输出：
```
📊 共 96 个文件，需要创建 2 个笔记本

📦 批次 1/2
📁 文件范围: 1-50 (共 50 个)
📚 创建笔记本: 火山引擎GPU云服务器文档

📦 批次 2/2
📁 文件范围: 51-96 (共 46 个)
📚 创建笔记本: 火山引擎GPU云服务器文档 (2)
```

### 自定义延迟

不同网站的速率限制不同：

```bash
# 保守设置（避免被封）
python scripts/download_markdown.py \
    --input links.json \
    --output docs/ \
    --delay 3.0

# 激进设置（快速抓取）
python scripts/download_markdown.py \
    --input links.json \
    --output docs/ \
    --delay 0.5
```

## 🐛 常见问题

### 1. Playwright 浏览器未安装

```bash
playwright install chromium
```

### 2. 提取不到链接

尝试使用 `--headless` 选项，或者不使用无头模式查看浏览器行为：

```bash
python scripts/extract_sidebar_iterative.py \
    "https://docs.example.com" \
    --output links.json
```

### 3. 上传失败

- 检查是否已登录 NotebookLM: `notebooklm status`
- 减小 `--delay` 参数值
- 查看失败文件列表: `_failed_uploads.txt`

### 4. 文件内容不完整

某些网站使用 JavaScript 动态加载内容，需要增加 `--delay` 参数：

```bash
python scripts/extract_sidebar_iterative.py \
    "https://docs.example.com" \
    --output links.json \
    --delay 3.0
```

## 📝 输出文件

### 链接提取阶段
- `links.json`: 所有文档链接（JSON 格式）
- `links.txt`: 所有文档链接（文本格式）
- `extract_progress.json`: 提取进度（支持断点续传）

### 下载阶段
- `docs/`: 所有 Markdown 文件
- `README.md`: 生成的目录索引
- `download_progress.json`: 下载进度

### 上传阶段
- `.notebooklm_info.json`: 笔记本 ID 信息
- `.upload_summary.json`: 上传摘要
- `_failed_uploads.txt`: 失败文件列表

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 开发建议

1. 遵循 PEP 8 代码风格
2. 添加类型注解
3. 编写文档字符串
4. 更新 README 示例

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [NotebookLM CLI](https://github.com/notebooklm/cli) - NotebookLM 命令行工具
- [Playwright](https://playwright.dev/) - Python 浏览器自动化
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML 解析

## 📮 联系方式

- GitHub Issues: [提交问题](https://github.com/yourusername/docs-to-notebooklm/issues)
- 讨论: [GitHub Discussions](https://github.com/yourusername/docs-to-notebooklm/discussions)

---

Made with ❤️ by the open-source community
