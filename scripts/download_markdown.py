#!/usr/bin/env python3
"""
Batch Download Documentation as Markdown

Downloads documentation pages from link list and converts to Markdown files.
Supports multiple sites with different fetching strategies.

Usage:
    python scripts/download_markdown.py \
        --input links.txt \
        --output output_dir/ \
        --delay 1.5
"""

import os
import re
import sys
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# Import html2text for markdown conversion
try:
    import html2text
except ImportError:
    html2text = None
    print("⚠ Warning: html2text not installed. Install with: pip install html2text")


class MarkdownDownloader:
    """Download documentation pages and convert to Markdown."""

    def __init__(
        self,
        input_file: str,
        output_dir: str,
        delay: float = 1.5,
        concurrent: int = 1,
        max_files: int = None,
        resume: bool = True,
        use_playwright: bool = False,
        cookie: Optional[str] = None
    ):
        """
        Initialize the markdown downloader.

        Args:
            input_file: Path to links file (text or JSON format)
            output_dir: Directory to save markdown files
            delay: Delay between downloads in seconds (default: 1.5)
            concurrent: Number of concurrent downloads (default: 1)
            max_files: Maximum number of files to download (default: all)
            resume: Resume from progress if interrupted (default: True)
            use_playwright: Use Playwright for downloading (default: False)
            cookie: Optional cookie for authentication
        """
        self.input_file = Path(input_file)
        self.output_dir = Path(output_dir)
        self.delay = delay
        self.concurrent = concurrent
        self.max_files = max_files
        self.resume = resume
        self.use_playwright = use_playwright
        self.cookie = cookie

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Tracking
        self.links: List[Dict] = []
        self.completed: set = set()
        self.failed: List[Dict] = []
        self.progress_file = self.output_dir / ".download_progress.json"

    def load_links(self):
        """Load links from input file (supports text and JSON formats)."""
        print(f"📖 读取链接文件: {self.input_file}")

        if not self.input_file.exists():
            raise FileNotFoundError(f"链接文件不存在: {self.input_file}")

        content = self.input_file.read_text(encoding='utf-8')

        # Try JSON format first
        try:
            data = json.loads(content)
            if isinstance(data, dict) and 'links' in data:
                self.links = data['links']
            elif isinstance(data, list):
                self.links = data
            else:
                raise ValueError("无法识别的 JSON 格式")
            print(f"  ✓ JSON 格式: {len(self.links)} 个链接")
        except json.JSONDecodeError:
            # Try text format
            self.links = self._parse_text_links(content)
            print(f"  ✓ 文本格式: {len(self.links)} 个链接")

        if self.max_files:
            self.links = self.links[:self.max_files]
            print(f"  ✓ 限制下载: {self.max_files} 个文件")

    def _parse_text_links(self, content: str) -> List[Dict]:
        """Parse links from text format (title + URL pattern)."""
        links = []
        current_title = None
        current_url = None

        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Check if line is a URL
            if line.startswith('http'):
                current_url = line
                if current_title:
                    links.append({'title': current_title, 'url': current_url})
                    current_title = None
                    current_url = None
            # Check if line is a numbered item (title)
            elif re.match(r'^\d+\.', line):
                # Remove number prefix
                title = re.sub(r'^\d+\.\s*', '', line)
                current_title = title
            # Check if line is indented (URL)
            elif line.startswith('   ') or line.startswith('\t'):
                current_url = line.strip()
                if current_title:
                    links.append({'title': current_title, 'url': current_url})
                    current_title = None
                    current_url = None
            # Plain line (title)
            else:
                if current_url:
                    links.append({'title': current_title or line, 'url': current_url})
                    current_url = None
                current_title = line

        return links

    def load_progress(self):
        """Load download progress if resuming."""
        if not self.resume or not self.progress_file.exists():
            return

        try:
            data = json.loads(self.progress_file.read_text(encoding='utf-8'))
            self.completed = set(data.get('completed', []))
            self.failed = data.get('failed', [])
            print(f"✓ 已完成: {len(self.completed)} 个文件")
            if self.failed:
                print(f"✗ 失败: {len(self.failed)} 个文件")
        except Exception as e:
            print(f"⚠ 无法读取进度文件: {e}")

    def save_progress(self):
        """Save download progress."""
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'total': len(self.links),
                'completed': list(self.completed),
                'failed': self.failed
            }
            self.progress_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        except Exception as e:
            print(f"⚠ 保存进度失败: {e}")

    def sanitize_filename(self, title: str) -> str:
        """Convert title to valid filename."""
        # Remove invalid characters
        invalid_chars = '<>:"/\\|?*'
        filename = title
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        # Remove leading/trailing spaces and dots
        filename = filename.strip('. ')

        # Limit length
        if len(filename) > 200:
            filename = filename[:200]

        return filename or 'untitled'

    def categorize_link(self, link: Dict) -> str:
        """Determine category/subdirectory for a link."""
        url = link['url']

        if '/api-' in url:
            return 'API参考'
        elif '/productdesc-' in url:
            return '产品描述'
        elif '/ug-' in url:
            return '用户指南'
        elif '/bestpractice-' in url:
            return '最佳实践'
        elif '/faq-' in url:
            return '常见问题'
        elif '/price-' in url:
            return '计费说明'
        else:
            return '其他文档'

    def fetch_page_html(self, url: str) -> Optional[str]:
        """Fetch page HTML using requests or Playwright."""
        if self.use_playwright:
            return self._fetch_with_playwright(url)
        else:
            return self._fetch_with_requests(url)

    def _fetch_with_requests(self, url: str) -> Optional[str]:
        """Fetch page using requests library."""
        try:
            import requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }

            if self.cookie:
                headers['Cookie'] = self.cookie

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding

            return response.text
        except Exception as e:
            print(f"    ✗ 请求失败: {e}")
            return None

    def _fetch_with_playwright(self, url: str) -> Optional[str]:
        """Fetch page using Playwright (for sites with captcha/js)."""
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )

                # Set cookie if provided
                if self.cookie:
                    domain = urlparse(url).netloc
                    if '=' in self.cookie:
                        name, value = self.cookie.split('=', 1)
                        context.add_cookies([{
                            'name': name.strip(),
                            'value': value.strip(),
                            'domain': domain,
                            'path': '/'
                        }])

                page = context.new_page()
                page.goto(url, wait_until='networkidle', timeout=30000)

                # Wait for dynamic content
                import time
                time.sleep(2)

                html = page.content()
                browser.close()

                return html
        except Exception as e:
            print(f"    ✗ Playwright 失败: {e}")
            return None

    def download_single_link(self, link: Dict, index: int, total: int) -> bool:
        """Download a single link and save as markdown."""
        title = link.get('title', 'untitled')
        url = link['url']

        # Skip if already completed
        if url in self.completed:
            return True

        print(f"  [{index+1}/{total}] {title[:60]}... ", end='', flush=True)

        try:
            # 1. Fetch HTML
            html = self.fetch_page_html(url)
            if not html:
                self.failed.append({'url': url, 'title': title, 'error': 'Failed to fetch'})
                print("✗")
                return False

            # 2. Extract main content
            soup = BeautifulSoup(html, 'html.parser')

            # Remove unwanted elements first
            for selector in [
                'nav', '.sidebar', '.navigation', '.menu', '.breadcrumb',
                'header', 'footer', '.header', '.footer',
                '.pagination', '.page-nav', '.edit-link',
                'script', 'style', '.code-block-copy-btn', '.line-numbers'
            ]:
                for element in soup.select(selector):
                    element.decompose()

            # Try to find main content area
            content_selectors = [
                'main',
                'article',
                '.content',
                '.doc-content',
                '.markdown-body',
                '[role="main"]',
                '.doc-body',
                '.documentation'
            ]

            content_element = None
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    break

            if content_element:
                content_html = str(content_element)
            else:
                # Fallback: use entire body (without nav/header/footer which we already removed)
                body = soup.find('body')
                content_html = str(body) if body else html

            # 3. Convert to Markdown
            if html2text:
                converter = html2text.HTML2Text()
                converter.ignore_links = False
                converter.ignore_images = False
                converter.ignore_emphasis = False
                converter.body_width = 0  # Don't wrap lines
                converter.unicode_snob = True
                converter.skip_internal_links = False
                markdown = converter.handle(content_html)
            else:
                # Fallback: simple HTML to text
                from html.parser import HTMLParser
                class HTMLToText(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.text = []
                    def handle_data(self, data):
                        self.text.append(data)
                parser = HTMLToText()
                parser.feed(content_html)
                markdown = '\n'.join(parser.text)

            # 4. Determine subdirectory
            category = self.categorize_link(link)
            output_subdir = self.output_dir / category
            output_subdir.mkdir(parents=True, exist_ok=True)

            # 5. Save file
            filename = self.sanitize_filename(title) + '.md'
            output_path = output_subdir / filename

            # Add metadata header
            full_markdown = f"""---
title: {title}
source: {url}
downloaded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

{markdown}
"""

            output_path.write_text(full_markdown, encoding='utf-8')

            self.completed.add(url)
            print("✓")

            # Delay between requests
            if self.delay > 0:
                time.sleep(self.delay)

            return True

        except Exception as e:
            error_msg = str(e)[:100]
            self.failed.append({'url': url, 'title': title, 'error': error_msg})
            print(f"✗ ({error_msg})")
            return False

    def download_all(self):
        """Download all links."""
        print("\n" + "="*60)
        print("📥 批量下载 Markdown 文档")
        print("="*60)
        print(f"输入文件: {self.input_file}")
        print(f"输出目录: {self.output_dir}")
        print(f"延迟: {self.delay}s")
        print(f"并发: {self.concurrent}")
        print(f"使用 Playwright: {self.use_playwright}")
        print("="*60)
        print()

        # Load links and progress
        self.load_links()
        self.load_progress()

        remaining = [link for link in self.links if link['url'] not in self.completed]
        print(f"待下载: {len(remaining)} 个文件")
        print()

        # Download sequentially for now (can add concurrency later)
        for i, link in enumerate(remaining):
            self.download_single_link(link, i, len(remaining))

            # Save progress every 10 files
            if (i + 1) % 10 == 0:
                self.save_progress()
                print(f"  📊 进度已保存 ({i+1}/{len(remaining)})")

        # Final save
        self.save_progress()

        # Generate report
        self.generate_report()

    def generate_report(self):
        """Generate download report."""
        print()
        print("="*60)
        print("📊 下载完成")
        print("="*60)
        print(f"总计: {len(self.links)} 个链接")
        print(f"成功: {len(self.completed)} 个")
        print(f"失败: {len(self.failed)} 个")
        print()

        # Save failed URLs
        if self.failed:
            failed_file = self.output_dir / "_failed_urls.txt"
            with open(failed_file, 'w', encoding='utf-8') as f:
                f.write("# 下载失败的链接\n\n")
                for item in self.failed:
                    f.write(f"- {item['title']}\n")
                    f.write(f"  URL: {item['url']}\n")
                    f.write(f"  错误: {item['error']}\n\n")
            print(f"✓ 失败列表已保存: {failed_file}")

        # Generate README
        readme_file = self.output_dir / "README.md"
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(f"# 文档归档\n\n")
            f.write(f"- **来源**: {self.input_file.name}\n")
            f.write(f"- **下载时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **总计**: {len(self.links)} 个文档\n")
            f.write(f"- **成功**: {len(self.completed)}\n")
            f.write(f"- **失败**: {len(self.failed)}\n\n")

            # List categories
            categories = {}
            for link in self.links:
                cat = self.categorize_link(link)
                categories[cat] = categories.get(cat, 0) + 1

            f.write("## 文档分类\n\n")
            for cat, count in sorted(categories.items()):
                f.write(f"- **{cat}**: {count} 个\n")

        print(f"✓ README 已生成: {readme_file}")
        print(f"✓ 输出目录: {self.output_dir}")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Batch download documentation as Markdown',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Download with default settings
  %(prog)s --input links.txt --output docs/

  # Download from Huawei Cloud (with Playwright)
  %(prog)s --input huawei_links.txt --output huawei_docs/ \\
      --use-playwright --delay 2.0

  # Resume interrupted download
  %(prog)s --input links.txt --output docs/ --resume

  # Download only first 10 files (test)
  %(prog)s --input links.txt --output test/ --max-files 10
        '''
    )

    parser.add_argument('--input', required=True,
                       help='Input links file (text or JSON)')
    parser.add_argument('--output', required=True,
                       help='Output directory for markdown files')
    parser.add_argument('--delay', type=float, default=1.5,
                       help='Delay between downloads in seconds (default: 1.5)')
    parser.add_argument('--concurrent', type=int, default=1,
                       help='Number of concurrent downloads (default: 1)')
    parser.add_argument('--max-files', type=int,
                       help='Maximum number of files to download')
    parser.add_argument('--no-resume', action='store_true',
                       help='Do not resume from progress')
    parser.add_argument('--use-playwright', action='store_true',
                       help='Use Playwright for downloading (slower but handles captcha)')
    parser.add_argument('--cookie',
                       help='Authentication cookie (e.g., tads_cap=xxxxx)')

    args = parser.parse_args()

    downloader = MarkdownDownloader(
        input_file=args.input,
        output_dir=args.output,
        delay=args.delay,
        concurrent=args.concurrent,
        max_files=args.max_files,
        resume=not args.no_resume,
        use_playwright=args.use_playwright,
        cookie=args.cookie
    )

    try:
        downloader.download_all()
    except KeyboardInterrupt:
        print("\n\n⚠ 下载被中断")
        print("✓ 进度已保存，使用 --resume 可继续下载")
        sys.exit(0)


if __name__ == '__main__':
    main()
