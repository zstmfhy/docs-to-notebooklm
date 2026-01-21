#!/usr/bin/env python3
"""
Iterative Sidebar Extractor with Playwright

Extracts sidebar navigation by clicking through each link iteratively.
Designed for sites with anti-scraping mechanisms like Huawei Cloud.

Requirements:
    pip install playwright
    playwright install chromium
"""

import asyncio
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set, Optional
from urllib.parse import urljoin, urlparse


class IterativeSidebarExtractor:
    """Extract sidebar links by iteratively clicking through navigation."""

    def __init__(
        self,
        start_url: str,
        output_file: Optional[str] = None,
        cookie: Optional[str] = None,
        delay: float = 1.0,
        max_pages: int = 1000,
        headless: bool = False,
        save_progress: bool = True
    ):
        """
        Initialize the iterative extractor.

        Args:
            start_url: Starting documentation page URL
            output_file: File to save extracted links (JSON format)
            cookie: Optional authentication cookie (e.g., 'tads_cap=xxxxx')
            delay: Delay between page loads in seconds (default: 1.0)
            max_pages: Maximum number of pages to visit (default: 1000)
            headless: Run browser in headless mode (default: False)
            save_progress: Save progress to file for resume capability (default: True)
        """
        self.start_url = start_url
        self.output_file = output_file or f"sidebar_links_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.cookie = cookie
        self.delay = delay
        self.max_pages = max_pages
        self.headless = headless
        self.save_progress = save_progress

        # Tracking sets
        self.visited_urls: Set[str] = set()
        self.sidebar_links: List[Dict] = []
        self.failed_urls: List[Dict] = []

        # Progress file
        self.progress_file = Path(self.output_file).stem + "_progress.json"

    async def extract_sidebar_links(self, page) -> List[Dict]:
        """
        Extract all sidebar links from current page.

        Returns:
            List of dicts with 'title' and 'url' keys
        """
        try:
            # Try multiple selectors for sidebar
            selectors = [
                'aside.sidebar a',
                'aside#left-nav a',
                '.nav-tree a',
                '.sidebar-nav a',
                '.doc-tree a',
                '.navigation a',
                'aside.VPSidebar a',  # VitePress
                '.menu a',  # Docusaurus
            ]

            links = []
            for selector in selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        for element in elements:
                            title = await element.inner_text()
                            url = await element.get_attribute('href')
                            if title and url:
                                # Clean title
                                title = title.strip()
                                # Convert relative URLs to absolute
                                if url.startswith('/'):
                                    base = f"{urlparse(self.start_url).scheme}://{urlparse(self.start_url).netloc}"
                                    url = urljoin(base, url)

                                links.append({
                                    'title': title,
                                    'url': url,
                                    'selector': selector
                                })
                        if links:
                            break  # Found links with this selector
                except:
                    continue

            return links
        except Exception as e:
            print(f"  ⚠ Error extracting links: {e}")
            return []

    async def visit_page_and_extract(self, page, url: str) -> bool:
        """
        Visit a page and extract its sidebar links.

        Returns:
            True if successful, False otherwise
        """
        if url in self.visited_urls:
            return False

        try:
            print(f"  → Visiting: {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(self.delay)

            # Extract sidebar links from this page
            links = await self.extract_sidebar_links(page)

            # Add new links
            new_links_count = 0
            for link in links:
                if link['url'] not in self.visited_urls:
                    self.sidebar_links.append(link)
                    self.visited_urls.add(link['url'])
                    new_links_count += 1

            print(f"    Found {len(links)} links, {new_links_count} new")
            return True

        except Exception as e:
            print(f"  ✗ Failed to visit {url}: {e}")
            self.failed_urls.append({'url': url, 'error': str(e)})
            return False

    async def load_progress(self):
        """Load previously saved progress."""
        if not self.save_progress:
            return

        progress_file = Path(self.progress_file)
        if not progress_file.exists():
            return

        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.visited_urls = set(data.get('visited_urls', []))
                self.sidebar_links = data.get('sidebar_links', [])
                self.failed_urls = data.get('failed_urls', [])
                print(f"✓ Loaded progress: {len(self.visited_urls)} URLs already visited")
        except Exception as e:
            print(f"⚠ Could not load progress: {e}")

    async def save_progress_sync(self):
        """Save current progress to file."""
        if not self.save_progress:
            return

        try:
            data = {
                'start_url': self.start_url,
                'visited_urls': list(self.visited_urls),
                'sidebar_links': self.sidebar_links,
                'failed_urls': self.failed_urls,
                'timestamp': datetime.now().isoformat()
            }
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠ Could not save progress: {e}")

    async def crawl(self):
        """
        Main crawling loop: visit each sidebar link iteratively.

        Returns:
            List of unique sidebar links
        """
        # Load previous progress if exists
        await self.load_progress()

        async with __import__('playwright.async_api', fromlist=['async_playwright']).async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )

            # Set cookie if provided
            if self.cookie:
                domain = urlparse(self.start_url).netloc
                # Parse cookie string (format: "name=value" or "name=value; domain=xxx")
                if '=' in self.cookie:
                    cookie_name, cookie_value = self.cookie.split('=', 1)
                    await context.add_cookies([{
                        'name': cookie_name.strip(),
                        'value': cookie_value.strip(),
                        'domain': domain,
                        'path': '/'
                    }])
                    print(f"✓ Set cookie: {cookie_name}")

            page = await context.new_page()

            # Visit start page
            print(f"\n🚀 Starting crawl from: {self.start_url}")
            await page.goto(self.start_url, wait_until='networkidle', timeout=30000)

            # Wait for manual captcha completion if needed
            if not self.headless:
                print("\n" + "="*60)
                print("⚠ Browser launched. Please complete any captcha/verification.")
                print("⚠ Press Enter in this terminal after verification is complete...")
                print("="*60)
                input()  # Wait for user to press Enter

            # Extract initial sidebar links
            print("\n📋 Extracting initial sidebar...")
            initial_links = await self.extract_sidebar_links(page)

            for link in initial_links:
                if link['url'] not in self.visited_urls:
                    self.sidebar_links.append(link)
                    self.visited_urls.add(link['url'])

            print(f"✓ Found {len(initial_links)} initial links")

            # Iteratively visit each link
            print(f"\n🔄 Iteratively visiting sidebar links...")

            index = 0
            while index < len(self.sidebar_links) and len(self.visited_urls) < self.max_pages:
                link = self.sidebar_links[index]
                success = await self.visit_page_and_extract(page, link['url'])

                if success:
                    # Save progress every 10 pages
                    if (index + 1) % 10 == 0:
                        await self.save_progress_sync()
                        print(f"  �� Progress: {index + 1}/{len(self.sidebar_links)} links processed")

                index += 1

            # Final save
            await self.save_progress_sync()

            # Close browser
            await browser.close()

        # Save results
        self.save_results()

        return self.sidebar_links

    def save_results(self):
        """Save extracted links to output file."""
        results = {
            'start_url': self.start_url,
            'total_links': len(self.sidebar_links),
            'total_visited': len(self.visited_urls),
            'failed_count': len(self.failed_urls),
            'timestamp': datetime.now().isoformat(),
            'links': self.sidebar_links,
            'failed_urls': self.failed_urls
        }

        # Save JSON
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        # Save human-readable text
        txt_file = Path(self.output_file).stem + '.txt'
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(f"# 侧边栏链接提取结果\n\n")
            f.write(f"来源: {self.start_url}\n")
            f.write(f"提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"总链接数: {len(self.sidebar_links)}\n")
            f.write(f"已访问: {len(self.visited_urls)}\n")
            f.write(f"失败: {len(self.failed_urls)}\n\n")
            f.write("---\n\n")

            for i, link in enumerate(self.sidebar_links, 1):
                f.write(f"{i}. {link['title']}\n")
                f.write(f"   {link['url']}\n\n")

        print(f"\n✓ Results saved to:")
        print(f"  - {self.output_file} (JSON)")
        print(f"  - {txt_file} (Text)")
        if self.failed_urls:
            print(f"\n✗ Failed URLs: {len(self.failed_urls)}")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Extract sidebar links iteratively using Playwright'
    )
    parser.add_argument('url', help='Starting documentation page URL')
    parser.add_argument('-o', '--output', default='sidebar_links.json',
                       help='Output JSON file (default: sidebar_links.json)')
    parser.add_argument('-c', '--cookie', help='Authentication cookie (e.g., tads_cap=xxxxx)')
    parser.add_argument('-d', '--delay', type=float, default=1.0,
                       help='Delay between page loads in seconds (default: 1.0)')
    parser.add_argument('-m', '--max-pages', type=int, default=1000,
                       help='Maximum number of pages to visit (default: 1000)')
    parser.add_argument('--headless', action='store_true',
                       help='Run browser in headless mode')
    parser.add_argument('--no-progress', action='store_true',
                       help='Do not save progress for resume')

    args = parser.parse_args()

    extractor = IterativeSidebarExtractor(
        start_url=args.url,
        output_file=args.output,
        cookie=args.cookie,
        delay=args.delay,
        max_pages=args.max_pages,
        headless=args.headless,
        save_progress=not args.no_progress
    )

    print("="*60)
    print("📚 Iterative Sidebar Extractor")
    print("="*60)
    print(f"Start URL: {args.url}")
    print(f"Output: {args.output}")
    print(f"Delay: {args.delay}s")
    print(f"Max pages: {args.max_pages}")
    print(f"Headless: {args.headless}")
    print("="*60)

    # Run async crawler
    asyncio.run(extractor.crawl())


if __name__ == '__main__':
    main()
