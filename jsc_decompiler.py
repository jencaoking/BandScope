"""
.jsc 字节码反编译模块

支持识别和处理多种字节码格式：
- V8 compiled bytecode / snapshot
- QuickJS bytecode
- JerryScript bytecode
- 自定义格式
"""

import struct
import os
import subprocess
import tempfile
import json
from pathlib import Path
from enum import Enum
from typing import Optional


class BytecodeType(Enum):
    UNKNOWN = "unknown"
    V8_SNAPSHOT = "v8_snapshot"
    V8_CODE_CACHE = "v8_code_cache"
    QUICKJS = "quickjs"
    JERRYSCRIPT = "jerryscript"
    CUSTOM = "custom"


class JSCDecompiler:
    """JSC 字节码反编译器"""

    # 已知的字节码魔数
    MAGIC_NUMBERS = {
        b'\xc0\xde\x01\x00': BytecodeType.V8_SNAPSHOT,
        b'\xc0\xde': BytecodeType.V8_CODE_CACHE,
        b'qjs\x00': BytecodeType.QUICKJS,
        b'JS\x00\x00': BytecodeType.JERRYSCRIPT,
    }

    def __init__(self, node_path: str = "node"):
        self.node_path = node_path

    def detect_type(self, filepath: str) -> BytecodeType:
        """检测 .jsc 文件的字节码类型"""
        with open(filepath, 'rb') as f:
            header = f.read(16)

        for magic, btype in self.MAGIC_NUMBERS.items():
            if header.startswith(magic):
                return btype

        # 进一步分析头部特征
        if self._check_v8_features(header):
            return BytecodeType.V8_SNAPSHOT
        if self._check_quickjs_features(filepath):
            return BytecodeType.QUICKJS

        return BytecodeType.UNKNOWN

    def _check_v8_features(self, header: bytes) -> bool:
        """检查是否为 V8 格式"""
        # V8 字节码通常在头部包含版本号
        if len(header) >= 8:
            # 检查是否包含合理的 V8 版本号
            version = struct.unpack('<I', header[4:8])[0]
            if 10000 < version < 20000:  # V8 版本号范围
                return True
        return False

    def _check_quickjs_features(self, filepath: str) -> bool:
        """检查是否为 QuickJS 格式"""
        try:
            size = os.path.getsize(filepath)
            # QuickJS 字节码有特定的大小和结构特征
            with open(filepath, 'rb') as f:
                header = f.read(4)
                # QuickJS 字节码标记
                if header == b'qjs\x00':
                    return True
                # 某些变体的标记
                if header[:3] == b'qjs':
                    return True
        except Exception:
            pass
        return False

    def decompile(self, filepath: str) -> Optional[str]:
        """反编译 .jsc 文件"""
        btype = self.detect_type(filepath)

        print(f"  检测到字节码类型: {btype.value}")

        decompile_methods = {
            BytecodeType.V8_SNAPSHOT: self._decompile_v8_snapshot,
            BytecodeType.V8_CODE_CACHE: self._decompile_v8_cache,
            BytecodeType.QUICKJS: self._decompile_quickjs,
            BytecodeType.JERRYSCRIPT: self._decompile_jerryscript,
            BytecodeType.UNKNOWN: self._decompile_generic,
        }

        method = decompile_methods.get(btype,
                                        self._decompile_generic)
        return method(filepath)

    def _decompile_v8_snapshot(self,
                                filepath: str) -> Optional[str]:
        """反编译 V8 snapshot 字节码"""
        script = f"""
const v8 = require('v8');
const vm = require('vm');
const fs = require('fs');

try {{
    const bytecode = fs.readFileSync('{filepath.replace("\\", "\\\\")}');

    // 方法1: 尝试作为 cached data
    const script = new vm.Script('', {{ cachedData: bytecode }});
    if (script.cachedDataRejected === false) {{
        console.log(script.toString());
        process.exit(0);
    }}
}} catch(e) {{
    // 方法2: 尝试反序列化
    try {{
        const ctx = v8.deserialize(
            fs.readFileSync('{filepath.replace("\\", "\\\\")}')
        );
        console.log(JSON.stringify(ctx, null, 2));
    }} catch(e2) {{
        console.error('V8反编译失败: ' + e2.message);
        process.exit(1);
    }}
}}
"""
        return self._run_node_script(script)

    def _decompile_v8_cache(self,
                             filepath: str) -> Optional[str]:
        """反编译 V8 code cache"""
        # V8 code cache 通常需要特殊处理
        return self._decompile_v8_snapshot(filepath)

    def _decompile_quickjs(self,
                            filepath: str) -> Optional[str]:
        """
        反编译 QuickJS 字节码
        QuickJS 有开源的字节码格式，可以手动解析
        """
        try:
            return self._parse_quickjs_bytecode(filepath)
        except Exception as e:
            print(f"  QuickJS 解析失败: {e}")
            return self._try_external_tool(
                'quickjs-decompiler', filepath
            )

    def _parse_quickjs_bytecode(self,
                                  filepath: str) -> Optional[str]:
        """
        手动解析 QuickJS 字节码
        QuickJS 字节码格式是公开的，可以精确解析
        """
        with open(filepath, 'rb') as f:
            data = f.read()

        # QuickJS 字节码结构
        # 参考: quickjs/quickjs.c 中的 bc_read_* 函数

        pos = 0
        result_parts = []

        # 读取头部标记
        tag = data[pos:pos+4]
        pos += 4

        if tag != b'qjs\x00':
            # 可能是变体格式
            return None

        # 读取版本
        version = struct.unpack('>I', data[pos:pos+4])[0]
        pos += 4

        result_parts.append(
            f"// QuickJS Bytecode v{version}"
        )
        result_parts.append(
            f"// 文件大小: {len(data)} bytes"
        )
        result_parts.append("")

        # 解析字节码中的常量池和指令
        # 这里是简化的解析，完整的需要参考 quickjs 源码
        try:
            functions = self._parse_qjs_functions(data, pos)
            for func in functions:
                result_parts.append(
                    f"// Function: {func['name']}"
                )
                result_parts.append(
                    f"//   locals: {func['locals']}"
                )
                result_parts.append(
                    f"//   bytecode length: "
                    f"{func['bytecode_len']}"
                )
                result_parts.append("")
        except Exception:
            result_parts.append(
                "// [无法完整解析字节码指令]"
            )

        return '\n'.join(result_parts)

    def _parse_qjs_functions(self, data: bytes,
                              start: int) -> list:
        """解析 QuickJS 字节码中的函数定义"""
        functions = []
        pos = start

        try:
            while pos < len(data) - 4:
                # 读取标签
                tag = data[pos]
                pos += 1

                if tag == 0:  # end of bytecode
                    break

                # 简化的函数头解析
                if pos + 8 > len(data):
                    break

                # 读取函数名长度
                name_len = struct.unpack(
                    '<H', data[pos:pos+2]
                )[0]
                pos += 2

                if name_len > 0 and pos + name_len <= len(data):
                    name = data[pos:pos+name_len].decode(
                        'utf-8', errors='replace'
                    )
                    pos += name_len
                else:
                    name = '<anonymous>'

                # 跳过函数体（简化处理）
                locals_count = struct.unpack(
                    '<I', data[pos:pos+4]
                )[0] if pos + 4 <= len(data) else 0
                pos += 4

                bytecode_len = struct.unpack(
                    '<I', data[pos:pos+4]
                )[0] if pos + 4 <= len(data) else 0
                pos += 4

                functions.append({
                    'name': name,
                    'locals': locals_count,
                    'bytecode_len': bytecode_len,
                })

                # 跳过字节码体
                pos += bytecode_len

        except (struct.error, IndexError):
            pass

        return functions

    def _decompile_jerryscript(self,
                                filepath: str) -> Optional[str]:
        """反编译 JerryScript 字节码"""
        try:
            with open(filepath, 'rb') as f:
                data = f.read()

            result = []
            result.append(
                f"// JerryScript Bytecode"
            )
            result.append(
                f"// 文件大小: {len(data)} bytes"
            )
            result.append("")

            # JerryScript 字节码包含字面量池
            # 尝试提取字符串字面量
            strings = self._extract_strings(data)
            if strings:
                result.append("// 提取的字符串字面量:")
                for s in strings:
                    if len(s) > 2:
                        result.append(f'// "{s}"')

            return '\n'.join(result)

        except Exception as e:
            return f"// JerryScript 解析失败: {e}"

    def _decompile_generic(self,
                            filepath: str) -> Optional[str]:
        """通用反编译方法：尝试所有方法"""
        methods = [
            self._decompile_v8_snapshot,
            self._decompile_quickjs,
            self._decompile_jerryscript,
        ]

        for method in methods:
            try:
                result = method(filepath)
                if result and len(result) > 50:
                    return result
            except Exception:
                continue

        # 最后的手段：提取可读内容
        return self._extract_readable(filepath)

    def _extract_readable(self,
                           filepath: str) -> Optional[str]:
        """从二进制文件中提取可读内容"""
        with open(filepath, 'rb') as f:
            data = f.read()

        result = [
            f"// [通用提取模式]",
            f"// 文件大小: {len(data)} bytes",
            f"// 字节码类型: 未识别",
            "",
        ]

        # 提取可打印字符串
        strings = self._extract_strings(data, min_length=4)
        if strings:
            result.append("// === 提取的字符串 ===")
            for s in strings[:100]:
                result.append(f'"{s}"')
            result.append("")

        # 提取可能的 URL
        urls = self._extract_urls(data)
        if urls:
            result.append("// === 发现的 URL ===")
            for url in urls:
                result.append(url)
            result.append("")

        # 十六进制头部信息
        result.append("// === 文件头 (前 64 字节) ===")
        for i in range(0, min(64, len(data)), 16):
            hex_str = ' '.join(
                f'{b:02x}' for b in data[i:i+16]
            )
            ascii_str = ''.join(
                chr(b) if 32 <= b < 127 else '.'
                for b in data[i:i+16]
            )
            result.append(f"// {i:04x}: {hex_str:<48} {ascii_str}")

        return '\n'.join(result)

    def _extract_strings(self, data: bytes,
                          min_length: int = 3) -> list:
        """提取二进制数据中的可打印字符串"""
        strings = []
        current = []

        for byte in data:
            if 32 <= byte < 127:
                current.append(chr(byte))
            else:
                if len(current) >= min_length:
                    strings.append(''.join(current))
                current = []

        if len(current) >= min_length:
            strings.append(''.join(current))

        return strings

    def _extract_urls(self, data: bytes) -> list:
        """提取二进制数据中的 URL"""
        import re
        text = data.decode('ascii', errors='ignore')
        pattern = r'https?://[^\s<>"\')\]\\]+'
        return list(set(re.findall(pattern, text)))

    def _try_external_tool(self, tool_name: str,
                            filepath: str) -> Optional[str]:
        """尝试使用外部工具"""
        try:
            result = subprocess.run(
                [tool_name, filepath],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def _run_node_script(self, script: str) -> Optional[str]:
        """运行 Node.js 脚本"""
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.js', delete=False
            ) as f:
                f.write(script)
                script_path = f.name

            result = subprocess.run(
                [self.node_path, script_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            os.unlink(script_path)

            if result.returncode == 0:
                return result.stdout
            else:
                print(f"  Node.js 错误: {result.stderr}")
                return None

        except FileNotFoundError:
            print("  警告: 未找到 Node.js，"
                  "跳过 V8 反编译")
            return None
        except subprocess.TimeoutExpired:
            print("  警告: Node.js 脚本执行超时")
            return None
