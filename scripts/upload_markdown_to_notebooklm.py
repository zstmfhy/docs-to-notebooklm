#!/usr/bin/env python3
"""
Upload local Markdown files to NotebookLM

Uploads all Markdown files from a directory to NotebookLM.
Supports recursive directory traversal.

Usage:
    python scripts/upload_markdown_to_notebooklm.py \
        --input ~/Downloads/markdown_docs/ \
        --notebook "火山引擎 GPU 文档" \
        --yes
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import argparse


class MarkdownUploader:
    """Upload Markdown files to NotebookLM."""

    # NotebookLM file limit per notebook
    MAX_FILES_PER_NOTEBOOK = 50

    def __init__(
        self,
        input_dir: str,
        notebook_name: str,
        auto_approve: bool = False,
        delay: float = 0.5,
        pattern: str = "*.md",
        batch_size: int = 50
    ):
        """
        Initialize the uploader.

        Args:
            input_dir: Path to directory containing Markdown files
            notebook_name: Name for the NotebookLM notebook
            auto_approve: Skip confirmation prompt (default: False)
            delay: Delay between uploads in seconds
            pattern: File pattern to match (default: "*.md")
            batch_size: Number of files per notebook (default: 50, max 50)
        """
        self.input_dir = Path(input_dir)
        self.notebook_name = notebook_name
        self.auto_approve = auto_approve
        self.delay = delay
        self.pattern = pattern
        self.batch_size = min(batch_size, self.MAX_FILES_PER_NOTEBOOK)

        # Tracking
        self.files: List[Path] = []
        self.notebook_ids: List[str] = []
        self.uploaded: List[str] = []
        self.failed: List[Dict] = []

    def find_markdown_files(self):
        """Find all Markdown files in input directory."""
        print(f"📖 扫描目录: {self.input_dir}")

        if not self.input_dir.exists():
            raise FileNotFoundError(f"目录不存在: {self.input_dir}")

        # Find all .md files recursively
        self.files = sorted(self.input_dir.rglob(self.pattern))
        print(f"  ✓ 找到 {len(self.files)} 个 Markdown 文件")

    def confirm_action(self) -> bool:
        """Ask user for confirmation (unless auto_approve is set)."""
        if self.auto_approve:
            return True

        print("\n" + "="*60)
        print("⚠️  即将批量上传到 NotebookLM")
        print("="*60)
        print(f"笔记本名称: {self.notebook_name}")
        print(f"文件数量: {len(self.files)}")
        print(f"预计耗时: ~{len(self.files) * self.delay:.0f} 秒")
        print("="*60)
        print()

        response = input("确认上传? (yes/no): ").strip().lower()
        return response in ['yes', 'y', '是', '确认']

    def create_notebook(self, batch_num: int = 1) -> str:
        """
        Create NotebookLM notebook.

        Args:
            batch_num: Batch number for naming (default: 1)

        Returns:
            Notebook ID if successful, None otherwise
        """
        # Add suffix if multiple notebooks
        if batch_num > 1:
            notebook_name = f"{self.notebook_name} ({batch_num})"
        else:
            notebook_name = self.notebook_name

        print(f"\n📚 创建笔记本: {notebook_name}")

        try:
            result = subprocess.run(
                ['notebooklm', 'create', notebook_name],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                output = result.stdout
                if output:
                    print(f"  ✅ {output.strip()}")
                    notebook_id = self._save_notebook_info(output, notebook_name, batch_num)
                    return notebook_id
                return None
            else:
                print(f"  ✗ 创建失败: {result.stderr}")
                return None

        except FileNotFoundError:
            print("  ✗ 未找到 notebooklm 命令")
            print("  💡 请确保已安装 NotebookLM CLI")
            return None
        except Exception as e:
            print(f"  ✗ 错误: {e}")
            return None

    def _save_notebook_info(self, output: str, notebook_name: str, batch_num: int) -> str:
        """
        Save notebook info from create command output.

        Returns:
            Notebook ID
        """
        notebook_id = None
        try:
            if 'notebook' in output.lower():
                import re
                match = re.search(r'[a-f0-9-]{36}', output)
                if match:
                    notebook_id = match.group(0)
                    self.notebook_ids.append(notebook_id)
                    print(f"  📝 笔记本ID: {notebook_id}")

                    # Save to info file
                    info_file = Path('.notebooklm_info.json')
                    info_data = {}
                    if info_file.exists():
                        info_data = json.loads(info_file.read_text(encoding='utf-8'))

                    info_data[f'batch_{batch_num}'] = {
                        'notebook_name': notebook_name,
                        'notebook_id': notebook_id,
                        'created_at': datetime.now().isoformat()
                    }

                    info_file.write_text(json.dumps(info_data, indent=2), encoding='utf-8')
        except:
            pass

        return notebook_id

    def upload_file(self, file_path: Path, notebook_id: str) -> bool:
        """
        Upload a single file to NotebookLM.

        Args:
            file_path: Path to file to upload
            notebook_id: Target notebook ID

        Returns:
            True if successful, False otherwise
        """
        try:
            # Read file content
            content = file_path.read_text(encoding='utf-8')

            # Build command with notebook ID using /dev/stdin
            cmd = [
                'notebooklm', 'source', 'add',
                '-n', notebook_id,
                '--type', 'text',
                '--title', file_path.stem,
                '/dev/stdin'
            ]

            result = subprocess.run(
                cmd,
                input=content,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                self.uploaded.append(str(file_path))
                return True
            else:
                error = result.stderr.strip() if result.stderr else 'Unknown error'
                print(f"    错误: {error[:100]}")
                return False

        except Exception as e:
            print(f"    异常: {str(e)[:100]}")
            return False

    def upload_batch(self):
        """Upload all files to NotebookLM in batches."""
        print("\n" + "="*60)
        print("📤 批量上传 Markdown 到 NotebookLM")
        print("="*60)
        print(f"输入目录: {self.input_dir}")
        print(f"笔记本: {self.notebook_name}")
        print(f"文件模式: {self.pattern}")
        print(f"延迟: {self.delay}s")
        print(f"每批最多: {self.batch_size} 个文件")
        print("="*60)
        print()

        # Find files
        self.find_markdown_files()

        # Calculate number of batches needed
        total_files = len(self.files)
        num_batches = (total_files + self.batch_size - 1) // self.batch_size

        print(f"📊 共 {total_files} 个文件，需要创建 {num_batches} 个笔记本")
        print()

        # Confirm
        if not self.confirm_action():
            print("✗ 操作已取消")
            return

        # Process files in batches
        for batch_num in range(1, num_batches + 1):
            start_idx = (batch_num - 1) * self.batch_size
            end_idx = min(start_idx + self.batch_size, total_files)
            batch_files = self.files[start_idx:end_idx]

            print(f"\n{'='*60}")
            print(f"📦 批次 {batch_num}/{num_batches}")
            print(f"📁 文件范围: {start_idx + 1}-{end_idx} (共 {len(batch_files)} 个)")
            print(f"{'='*60}")

            # Create notebook for this batch
            notebook_id = self.create_notebook(batch_num)
            if not notebook_id:
                print(f"✗ 无法创建笔记本 {batch_num}，跳过此批次")
                # Mark all files in this batch as failed
                for file_path in batch_files:
                    self.failed.append({
                        'file': str(file_path),
                        'error': f'Failed to create notebook {batch_num}'
                    })
                continue

            # Upload files to this notebook
            print(f"\n🚀 开始上传 {len(batch_files)} 个文件到笔记本 {batch_num}...")
            print()

            for i, file_path in enumerate(batch_files, 1):
                # Show relative path for brevity
                rel_path = file_path.relative_to(self.input_dir)
                global_idx = start_idx + i
                print(f"[{global_idx}/{total_files}] {str(rel_path)[:60]}... ", end='', flush=True)

                success = self.upload_file(file_path, notebook_id)

                if success:
                    print("✓")
                else:
                    print("✗")
                    self.failed.append({
                        'file': str(file_path),
                        'error': 'Upload failed'
                    })

                # Delay between uploads
                if self.delay > 0 and i < len(batch_files):
                    time.sleep(self.delay)

                # Progress update every 10 uploads
                if i % 10 == 0:
                    print(f"\n  📊 批次进度: {i}/{len(batch_files)} 已上传\n")

            print(f"\n✓ 批次 {batch_num} 完成！")

        # Generate report
        self.generate_report()

    def generate_report(self):
        """Generate upload report."""
        print("\n" + "="*60)
        print("📊 上传完成")
        print("="*60)
        print(f"总计: {len(self.files)} 个文件")
        print(f"成功: {len(self.uploaded)} 个")
        print(f"失败: {len(self.failed)} 个")
        print(f"创建笔记本: {len(self.notebook_ids)} 个")
        print()

        # List all notebooks
        if self.notebook_ids:
            print("📚 已创建的笔记本:")
            for i, notebook_id in enumerate(self.notebook_ids, 1):
                notebook_name = self.notebook_name if i == 1 else f"{self.notebook_name} ({i})"
                print(f"  {i}. {notebook_name}")
                print(f"     ID: {notebook_id}")
            print()

        # Save failed files
        if self.failed:
            failed_file = Path('_failed_uploads.txt')
            with open(failed_file, 'w', encoding='utf-8') as f:
                f.write("# 上传失败的文件\n\n")
                for item in self.failed:
                    f.write(f"- {item['file']}\n")
                    f.write(f"  错误: {item['error']}\n\n")
            print(f"✓ 失败列表已保存: {failed_file}")

        # Save summary
        summary_file = Path('.upload_summary.json')
        summary_data = {
            'notebook_name': self.notebook_name,
            'notebooks': self.notebook_ids,
            'timestamp': datetime.now().isoformat(),
            'total_files': len(self.files),
            'uploaded': len(self.uploaded),
            'failed': len(self.failed),
            'batch_size': self.batch_size,
            'pattern': self.pattern
        }
        summary_file.write_text(
            json.dumps(summary_data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        print(f"✓ 上传摘要已保存: {summary_file}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Upload Markdown files to NotebookLM (supports multiple notebooks)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Upload all Markdown files (auto-split into 50-file batches)
  %(prog)s --input ~/Downloads/docs/ --notebook "My Docs"

  # Auto approve with faster upload
  %(prog)s --input ~/Downloads/docs/ --notebook "My Docs" --yes --delay 0.3

  # Custom batch size (max 50 for NotebookLM)
  %(prog)s --input ~/Downloads/docs/ --notebook "My Docs" --batch-size 40

Note:
  NotebookLM has a limit of 50 sources per notebook.
  This script automatically creates multiple notebooks when needed.
        '''
    )

    parser.add_argument('--input', required=True,
                       help='Input directory containing Markdown files')
    parser.add_argument('--notebook', required=True,
                       help='NotebookLM notebook name (will add suffix for multiple notebooks)')
    parser.add_argument('--pattern', default='*.md',
                       help='File pattern to match (default: *.md)')
    parser.add_argument('--yes', action='store_true',
                       help='Skip confirmation and auto-approve')
    parser.add_argument('--delay', type=float, default=0.5,
                       help='Delay between uploads in seconds (default: 0.5)')
    parser.add_argument('--batch-size', type=int, default=50,
                       help='Number of files per notebook (default: 50, max 50)')

    args = parser.parse_args()

    uploader = MarkdownUploader(
        input_dir=args.input,
        notebook_name=args.notebook,
        auto_approve=args.yes,
        delay=args.delay,
        pattern=args.pattern,
        batch_size=args.batch_size
    )

    try:
        uploader.upload_batch()
    except KeyboardInterrupt:
        print("\n\n⚠ 上传被中断")
        print(f"✓ 已上传: {len(uploader.uploaded)} 个文件")
        print(f"✓ 创建笔记本: {len(uploader.notebook_ids)} 个")
        sys.exit(0)


if __name__ == '__main__':
    main()
