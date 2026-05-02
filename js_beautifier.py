"""JS 美化模块"""

import os
from pathlib import Path
from typing import Optional


class JSBeautifier:
    """JS 代码美化器"""

    def __init__(self):
        self._jsbeautify = None
        try:
            import jsbeautifier
            self._jsbeautify = jsbeautifier
        except ImportError:
            pass

    def beautify(self, code: str) -> str:
        """美化 JS 代码"""
        if self._jsbeautify:
            opts = self._jsbeautify.default_options()
            opts.indent_size = 2
            opts.indent_char = ' '
            opts.max_preserve_newlines = 2
            opts.preserve_newlines = True
            opts.keep_array_indentation = False
            opts.break_chained_methods = False
            opts.space_before_conditional = True
            opts.unescape_strings = True
            return self._jsbeautify.beautify(code, opts)

        # 简单的内置美化（不需要外部依赖）
        return self._simple_beautify(code)

    def _simple_beautify(self, code: str) -> str:
        """简单的内置美化（无需依赖）"""
        result = []
        indent = 0
        i = 0

        while i < len(code):
            ch = code[i]

            if ch == '{':
                result.append(ch)
                result.append('\n')
                indent += 1
                result.append('  ' * indent)
            elif ch == '}':
                result.append('\n')
                indent -= 1
                result.append('  ' * indent)
                result.append(ch)
                if i + 1 < len(code) and code[i+1] not in (
                    ',', ';', ')'
                ):
                    result.append('\n')
                    result.append('  ' * indent)
            elif ch == ';':
                result.append(ch)
                result.append('\n')
                result.append('  ' * indent)
            elif ch in (' ', '\t', '\n', '\r'):
                # 保留单个空格
                if result and result[-1] != ' ':
                    result.append(' ')
                i += 1
                continue
            elif ch == '"' or ch == "'":
                # 保留字符串内容
                quote = ch
                result.append(ch)
                i += 1
                while i < len(code) and code[i] != quote:
                    if code[i] == '\\':
                        result.append(code[i])
                        i += 1
                        if i < len(code):
                            result.append(code[i])
                    else:
                        result.append(code[i])
                    i += 1
                if i < len(code):
                    result.append(code[i])
            else:
                result.append(ch)

            i += 1

        return ''.join(result)

    def beautify_file(self, filepath: str,
                       in_place: bool = True) -> str:
        """美化文件"""
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()

        beautified = self.beautify(code)

        if in_place:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(beautified)

        return beautified

    def beautify_directory(self, directory: str) -> int:
        """美化目录下所有 JS 文件"""
        count = 0
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.endswith(('.js', '.jsc')):
                    filepath = os.path.join(root, f)
                    try:
                        self.beautify_file(filepath)
                        count += 1
                    except Exception as e:
                        print(f"美化失败 {f}: {e}")
        return count
