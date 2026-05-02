"""UX 文件解析模块 - 处理 .ux 单文件组件"""

import os
import re
from pathlib import Path
from typing import Optional


class UXParser:
    """UX 文件解析器"""

    def __init__(self):
        # 匹配 <template>, <style>, <script> 标签
        self.section_patterns = {
            'template': re.compile(
                r'<template[^>]*>(.*?)</template>',
                re.DOTALL
            ),
            'style': re.compile(
                r'<style[^>]*>(.*?)</style>',
                re.DOTALL
            ),
            'script': re.compile(
                r'<script[^>]*>(.*?)</script>',
                re.DOTALL
            ),
        }

    def parse(self, ux_path: str) -> dict:
        """解析 .ux 文件，返回各部分内容"""
        with open(ux_path, 'r', encoding='utf-8') as f:
            content = f.read()

        result = {
            'template': '',
            'style': '',
            'script': '',
            'raw': content
        }

        for section, pattern in self.section_patterns.items():
            match = pattern.search(content)
            if match:
                result[section] = match.group(1).strip()

        return result

    def split(self, ux_path: str,
              output_dir: str) -> dict:
        """将 .ux 文件拆分为 .js / .xml / .css"""
        parsed = self.parse(ux_path)
        stem = Path(ux_path).stem
        os.makedirs(output_dir, exist_ok=True)

        result = {}

        if parsed['template']:
            xml_path = os.path.join(
                output_dir, f"{stem}.xml"
            )
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(parsed['template'])
            result['template'] = xml_path

        if parsed['style']:
            css_path = os.path.join(
                output_dir, f"{stem}.css"
            )
            with open(css_path, 'w', encoding='utf-8') as f:
                f.write(parsed['style'])
            result['style'] = css_path

        if parsed['script']:
            js_path = os.path.join(
                output_dir, f"{stem}.js"
            )
            with open(js_path, 'w', encoding='utf-8') as f:
                f.write(parsed['script'])
            result['script'] = js_path

        return result

    def find_groups(self, directory: str) -> list:
        """查找可合并的 .js/.xml/.css 文件组"""
        groups = []
        seen = set()

        for root, dirs, files in os.walk(directory):
            js_files = {
                f[:-3] for f in files if f.endswith('.js')
            }
            xml_files = {
                f[:-4] for f in files if f.endswith('.xml')
            }
            css_files = {
                f[:-4] for f in files if f.endswith('.css')
            }

            # 找到同时存在两种以上文件的基名
            all_names = js_files | xml_files | css_files
            for name in all_names:
                key = os.path.join(root, name)
                if key in seen:
                    continue
                seen.add(key)

                group = {'name': name, 'dir': root}
                if name in js_files:
                    group['js'] = os.path.join(
                        root, f"{name}.js"
                    )
                if name in xml_files:
                    group['xml'] = os.path.join(
                        root, f"{name}.xml"
                    )
                if name in css_files:
                    group['css'] = os.path.join(
                        root, f"{name}.css"
                    )

                if len(group) > 2:  # 至少有 name + dir + 1个文件
                    groups.append(group)

        return groups

    def merge(self, group: dict,
              output_dir: str) -> str:
        """将分离的文件合并为 .ux"""
        os.makedirs(output_dir, exist_ok=True)

        parts = []

        # Template
        if 'xml' in group and os.path.exists(group['xml']):
            with open(group['xml'], 'r',
                       encoding='utf-8') as f:
                content = f.read()
            parts.append(f"<template>\n{content}\n</template>")

        # Style
        if 'css' in group and os.path.exists(group['css']):
            with open(group['css'], 'r',
                       encoding='utf-8') as f:
                content = f.read()
            parts.append(f"<style>\n{content}\n</style>")

        # Script
        if 'js' in group and os.path.exists(group['js']):
            with open(group['js'], 'r',
                       encoding='utf-8') as f:
                content = f.read()
            parts.append(f"<script>\n{content}\n</script>")

        ux_content = '\n\n'.join(parts)
        ux_path = os.path.join(
            output_dir, f"{group['name']}.ux"
        )

        with open(ux_path, 'w', encoding='utf-8') as f:
            f.write(ux_content)

        return ux_path
