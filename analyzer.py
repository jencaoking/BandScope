"""RPK 静态分析模块"""

import os
import re
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional


class RPKAnalyzer:
    """RPK 静态分析器"""

    # API 调用模式
    API_PATTERNS = {
        'sensor': r'sensor\.\w+',
        'bluetooth': r'(?:bluetooth|ble|gatt)\.\w+',
        'storage': r'storage\.\w+',
        'network': r'(?:fetch|request)\s*\(',
        'vibrator': r'vibrator\.\w+',
        'router': r'router\.\w+',
        'file': r'(?:file)\.\w+',
        'notification': r'notification\.\w+',
        'alarm': r'alarm\.\w+',
        'battery': r'battery\.\w+',
        'device': r'device\.\w+',
    }

    # 敏感字符串模式
    SENSITIVE_PATTERNS = {
        'url': r'https?://[^\s<>"\')\]\\]+',
        'ip': r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
        'email': r'[\w.-]+@[\w.-]+\.\w+',
        'key': r'(?:api[_-]?key|token|secret|password)'
               r'\s*[:=]\s*["\'][^"\']+["\']',
        'uuid': r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}'
                r'-[0-9a-f]{4}-[0-9a-f]{12}',
    }

    def analyze_rpk(self, rpk_path: str) -> Optional[dict]:
        """分析 RPK 文件统计信息"""
        if not os.path.exists(rpk_path):
            return None

        stats = defaultdict(
            lambda: {'count': 0, 'size': 0}
        )

        try:
            with zipfile.ZipFile(rpk_path, 'r') as zf:
                for info in zf.infolist():
                    ext = Path(info.filename).suffix or '无扩展名'
                    stats[ext]['count'] += 1
                    stats[ext]['size'] += info.file_size
        except Exception:
            return None

        return dict(stats)

    def full_analysis(self, path: str) -> dict:
        """完整静态分析"""
        report = {
            'api_calls': Counter(),
            'strings': [],
            'urls': [],
            'hardcoded': {},
            'file_types': Counter(),
            'imports': [],
        }

        if path.endswith('.rpk'):
            # 解包到临时目录后分析
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                with zipfile.ZipFile(path, 'r') as zf:
                    zf.extractall(tmp)
                self._analyze_directory(tmp, report)
        elif os.path.isdir(path):
            self._analyze_directory(path, report)

        return report

    def _analyze_directory(self, directory: str,
                            report: dict):
        """分析目录中的所有文件"""
        for root, dirs, files in os.walk(directory):
            for filename in files:
                filepath = os.path.join(root, filename)
                ext = Path(filename).suffix.lower()
                report['file_types'][ext] += 1

                if ext in ('.js', '.ux'):
                    self._analyze_js_file(filepath, report)

    def _analyze_js_file(self, filepath: str,
                          report: dict):
        """分析单个 JS 文件"""
        try:
            with open(filepath, 'r', encoding='utf-8',
                       errors='ignore') as f:
                content = f.read()
        except Exception:
            return

        # API 调用统计
        for api_name, pattern in self.API_PATTERNS.items():
            matches = re.findall(pattern, content)
            for m in matches:
                report['api_calls'][m] += 1

        # URL 提取
        urls = re.findall(
            self.SENSITIVE_PATTERNS['url'], content
        )
        report['urls'].extend(urls)

        # 字符串提取
        strings = re.findall(
            r'["\']([^"\']{4,100})["\']', content
        )
        report['strings'].extend(strings)

        # import 提取
        imports = re.findall(
            r'import\s+.*?from\s+["\']([^"\']+)["\']',
            content
        )
        report['imports'].extend(imports)

        # 硬编码检测
        self._detect_hardcoded(content, report)

    def _detect_hardcoded(self, content: str,
                           report: dict):
        """检测硬编码值"""
        patterns = {
            'port': r'(?:port|PORT)\s*[:=]\s*(\d{2,5})',
            'timeout': r'(?:timeout|TIMEOUT)\s*[:=]\s*(\d+)',
            'version': r'(?:version|VERSION)\s*[:=]\s*'
                       r'["\']([^"\']+)["\']',
        }

        for key, pattern in patterns.items():
            matches = re.findall(pattern, content)
            if matches:
                report['hardcoded'][key] = matches[0]
