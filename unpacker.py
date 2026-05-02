"""RPK 解包模块"""

import zipfile
import os
import hashlib
from pathlib import Path


class RPKUnpacker:
    """RPK 文件解包器"""

    def __init__(self, rpk_path: str):
        self.rpk_path = rpk_path
        self._zip = None

    def validate(self) -> bool:
        """验证是否为合法的 RPK 文件"""
        if not os.path.exists(self.rpk_path):
            return False

        if not zipfile.is_zipfile(self.rpk_path):
            return False

        try:
            with zipfile.ZipFile(self.rpk_path, 'r') as zf:
                names = zf.namelist()
                # RPK 应该包含 manifest.json 或类似配置
                has_manifest = any(
                    'manifest' in n.lower() for n in names
                )
                # 或者包含 JS/JSX/UX 文件
                has_code = any(
                    n.endswith(('.js', '.jsc', '.ux'))
                    for n in names
                )
                return has_manifest or has_code
        except zipfile.BadZipFile:
            return False

    def get_file_list(self) -> list:
        """获取 RPK 内文件列表"""
        with zipfile.ZipFile(self.rpk_path, 'r') as zf:
            return zf.namelist()

    def unpack(self, output_dir: str) -> dict:
        """解包到指定目录"""
        os.makedirs(output_dir, exist_ok=True)

        with zipfile.ZipFile(self.rpk_path, 'r') as zf:
            zf.extractall(output_dir)

        file_count = sum(
            1 for _, _, files in os.walk(output_dir)
            for _ in files
        )

        return {
            'output_dir': output_dir,
            'file_count': file_count,
            'files': self.get_file_list()
        }

    def read_file(self, inner_path: str) -> bytes:
        """读取 RPK 内的单个文件"""
        with zipfile.ZipFile(self.rpk_path, 'r') as zf:
            return zf.read(inner_path)

    def read_text(self, inner_path: str,
                  encoding='utf-8') -> str:
        """读取 RPK 内的文本文件"""
        return self.read_file(inner_path).decode(encoding)

    def get_manifest(self) -> dict:
        """提取 manifest.json"""
        import json
        with zipfile.ZipFile(self.rpk_path, 'r') as zf:
            for name in zf.namelist():
                if 'manifest.json' in name:
                    data = zf.read(name)
                    return json.loads(data)
        return {}

    def get_hash(self) -> str:
        """计算 RPK 文件的 SHA256"""
        sha256 = hashlib.sha256()
        with open(self.rpk_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def list_by_type(self) -> dict:
        """按文件类型分类列出"""
        result = {}
        for name in self.get_file_list():
            ext = Path(name).suffix.lower() or '无扩展名'
            if ext not in result:
                result[ext] = []
            result[ext].append(name)
        return result
