"""manifest.json 解析模块"""

import json
import zipfile
import os
from typing import Optional


class ManifestParser:
    """RPK manifest 解析器"""

    def parse_rpk(self, rpk_path: str) -> Optional[dict]:
        """从 RPK 文件中解析 manifest"""
        try:
            with zipfile.ZipFile(rpk_path, 'r') as zf:
                for name in zf.namelist():
                    if name.endswith('manifest.json'):
                        data = zf.read(name)
                        return json.loads(data)
        except Exception as e:
            print(f"解析 manifest 失败: {e}")
        return None

    def parse_file(self, manifest_path: str) -> dict:
        """从文件解析 manifest"""
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_permissions(self, manifest: dict) -> list:
        """提取权限列表"""
        features = manifest.get('features', [])
        return [f.get('name', '') for f in features]

    def get_pages(self, manifest: dict) -> dict:
        """提取页面路由"""
        router = manifest.get('router', {})
        return router.get('pages', {})

    def get_entry(self, manifest: dict) -> str:
        """提取入口页面"""
        router = manifest.get('router', {})
        return router.get('entry', '')

    def get_platform_apis(self, manifest: dict) -> list:
        """提取使用的平台 API"""
        features = manifest.get('features', [])
        apis = []
        for f in features:
            name = f.get('name', '')
            if name.startswith('system.'):
                apis.append(name)
        return apis

    def to_readable(self, manifest: dict) -> str:
        """生成可读的清单描述"""
        lines = []
        lines.append(f"应用名称: {manifest.get('name', 'N/A')}")
        lines.append(f"包名: {manifest.get('package', 'N/A')}")
        lines.append(
            f"版本: {manifest.get('versionName', 'N/A')}"
            f" ({manifest.get('versionCode', 'N/A')})"
        )
        lines.append(
            f"最低平台版本: "
            f"{manifest.get('minPlatformVersion', 'N/A')}"
        )
        lines.append("")

        # 权限
        apis = self.get_platform_apis(manifest)
        if apis:
            lines.append("使用的平台 API:")
            for api in apis:
                lines.append(f"  • {api}")
            lines.append("")

        # 页面
        pages = self.get_pages(manifest)
        if pages:
            lines.append("页面路由:")
            entry = self.get_entry(manifest)
            for page, config in pages.items():
                marker = " (入口)" if page == entry else ""
                lines.append(
                    f"  • {page} -> "
                    f"{config.get('component', '?')}{marker}"
                )

        return '\n'.join(lines)
