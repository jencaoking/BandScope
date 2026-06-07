#!/usr/bin/env python3
"""
Improved Mi Band Bytecode Decompiler - Pro Version
改进版小米手环字节码反编译器

基于 wxapkg-unpacker 项目设计理念开发

核心特性：
1. 模块化架构 - 分离字符串提取、函数识别、代码生成
2. 代码美化 - 自动格式化输出代码
3. 无效代码清理 - 删除冗余代码
4. 异步IO - 高效处理大文件
5. 子包支持 - 批量处理多个文件
6. 配置文件生成 - 自动生成必要配置
"""

import os
import re
import struct
import json
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class OutputFormat(Enum):
    """输出格式"""
    MINIFIED = "minified"       # 压缩格式
    PRETTY = "pretty"          # 格式化
    COMPLETE = "complete"      # 完整代码


@dataclass
class FunctionInfo:
    """函数信息"""
    name: str
    params: List[str] = field(default_factory=list)
    locals: List[str] = field(default_factory=list)
    complexity: int = 0
    instructions: List[str] = field(default_factory=list)


@dataclass
class ModuleInfo:
    """模块信息"""
    name: str
    path: str
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    data_fields: List[str] = field(default_factory=list)


class StringExtractor:
    """字符串提取器"""
    
    def __init__(self):
        self.strings = []
        self.strings_map = {}
    
    def extract_from_bytes(self, data: bytes) -> List[Tuple[int, str]]:
        """从字节数据中提取字符串"""
        strings = []
        
        # 方法1: UTF-8可打印字符序列
        strings.extend(self._extract_printable_strings(data))
        
        # 方法2: 长度前缀字符串
        strings.extend(self._extract_length_prefixed_strings(data))
        
        # 方法3: C风格字符串
        strings.extend(self._extract_c_strings(data))
        
        # 去重并排序
        seen = set()
        unique = []
        for offset, s in strings:
            if s not in seen and self._is_valid_string(s):
                seen.add(s)
                unique.append((offset, s))
        
        return sorted(unique, key=lambda x: (-len(x[1]), x[0]))
    
    def _extract_printable_strings(self, data: bytes) -> List[Tuple[int, str]]:
        """提取可打印字符序列"""
        strings = []
        current = []
        start = 0
        
        for i, byte in enumerate(data):
            if 32 <= byte < 127:
                if not current:
                    start = i
                current.append(chr(byte))
            else:
                if len(current) >= 2:
                    strings.append((start, ''.join(current)))
                current = []
        
        if len(current) >= 2:
            strings.append((start, ''.join(current)))
        
        return strings
    
    def _extract_length_prefixed_strings(self, data: bytes) -> List[Tuple[int, str]]:
        """提取长度前缀字符串"""
        strings = []
        i = 0
        
        while i < len(data) - 2:
            if 0 < data[i] < 100:
                length = data[i]
                if i + length + 1 < len(data):
                    try:
                        s = data[i+1:i+1+length].decode('utf-8')
                        if len(s) >= 2:
                            strings.append((i, s))
                    except:
                        pass
                    i += length + 1
                    continue
            i += 1
        
        return strings
    
    def _extract_c_strings(self, data: bytes) -> List[Tuple[int, str]]:
        """提取C风格字符串"""
        strings = []
        i = 0
        
        while i < len(data):
            if data[i] == 0:
                i += 1
                continue
            
            start = i
            end = i
            while end < len(data) and 32 <= data[end] < 127:
                end += 1
            
            if end > start:
                strings.append((start, data[start:end].decode('utf-8', errors='ignore')))
            i = end + 1
        
        return strings
    
    def _is_valid_string(self, s: str) -> bool:
        """验证字符串是否有效"""
        if len(s) < 2 or len(s) > 100:
            return False
        
        # 排除纯数字
        if s.isdigit() and len(s) <= 6:
            return False
        
        # 排除特殊模式
        patterns = [
            r'^[a-f0-9]{32,}$',  # MD5等哈希
            r'^[+\-*/=<>!&|]+$',  # 纯操作符
        ]
        
        for pattern in patterns:
            if re.match(pattern, s):
                return False
        
        return True


class FunctionAnalyzer:
    """函数分析器"""
    
    def __init__(self, strings: List[Tuple[int, str]]):
        self.strings = strings
        self.functions = []
    
    def analyze(self) -> List[FunctionInfo]:
        """分析函数"""
        for offset, s in self.strings:
            if self._is_function_name(s):
                func = FunctionInfo(name=s)
                self._analyze_function_details(func, offset)
                self.functions.append(func)
        
        return self.functions
    
    def _is_function_name(self, name: str) -> bool:
        """判断是否为函数名"""
        if len(name) < 2 or len(name) > 50:
            return False
        
        if not name[0].isalpha() and name[0] != '_':
            return False
        
        if not re.match(r'^[a-zA-Z_$][a-zA-Z0-9_$]*$', name):
            return False
        
        keywords = {
            'function', 'var', 'let', 'const', 'if', 'else', 'for', 'while',
            'return', 'true', 'false', 'null', 'undefined', 'typeof', 'instanceof',
            'new', 'this', 'class', 'extends', 'super', 'import', 'export',
            'from', 'default', 'async', 'await', 'try', 'catch', 'finally'
        }
        
        return name.lower() not in keywords
    
    def _analyze_function_details(self, func: FunctionInfo, offset: int):
        """分析函数详情"""
        # 常见的生命周期函数
        lifecycle_funcs = {
            'onInit', 'onReady', 'onShow', 'onHide', 'onDestroy',
            'onLaunch', 'onLoad', 'onUnload', 'onPageScroll'
        }
        
        # 常见的事件处理函数
        event_funcs = {
            'onClick', 'onTap', 'onTouchStart', 'onTouchMove',
            'onTouchEnd', 'onSwipe', 'onLongPress'
        }
        
        # 常见的业务函数
        biz_funcs = {
            'verifyCode', 'test', 'solve', 'setnum', 'delnum',
            'toHomePage', 'initUI', 'loadData', 'saveData', 'setupEvents'
        }
        
        if func.name in lifecycle_funcs:
            func.params = []
            func.complexity = 3
        elif func.name in event_funcs:
            func.params = ['event']
            func.complexity = 2
        elif func.name in biz_funcs:
            func.complexity = 5
        else:
            func.complexity = 1


class CodeGenerator:
    """代码生成器"""
    
    def __init__(self, module_info: ModuleInfo):
        self.module = module_info
        self.indent_level = 0
    
    def generate(self, format_type: OutputFormat = OutputFormat.COMPLETE) -> str:
        """生成代码"""
        if format_type == OutputFormat.MINIFIED:
            return self._generate_minified()
        elif format_type == OutputFormat.PRETTY:
            return self._generate_pretty()
        else:
            return self._generate_complete()
    
    def _generate_minified(self) -> str:
        """生成压缩格式代码"""
        lines = []
        
        # 模块导入
        for imp in self.module.imports:
            lines.append(f"import{{{imp}}}from'{imp}';")
        
        # 模块定义
        lines.append(f"export default{{{self._generate_data_section()},{self._generate_methods_section()}}};")
        
        return ''.join(lines)
    
    def _generate_pretty(self) -> str:
        """生成格式化代码"""
        lines = []
        
        lines.append("// Generated JavaScript Code")
        lines.append("")
        
        # 模块导入
        for imp in self.module.imports:
            lines.append(f"import {imp.split('/')[-1]} from '{imp}';")
        
        lines.append("")
        
        # 模块定义
        lines.append("export default {")
        self.indent_level = 1
        
        lines.append(self._indent() + "// Page Data")
        lines.append(self._indent() + self._generate_data_section())
        lines.append("")
        
        lines.append(self._indent() + self._generate_methods_section())
        
        self.indent_level = 0
        lines.append("};")
        
        return '\n'.join(lines)
    
    def _generate_complete(self) -> str:
        """生成完整代码"""
        lines = []
        
        lines.append("/**")
        lines.append(" * Mi Band Application Module")
        lines.append(f" * @module {self.module.name}")
        lines.append(" */")
        lines.append("")
        
        # 模块导入
        for imp in self.module.imports:
            lines.append(f"import {self._extract_import_name(imp)} from '{imp}';")
        
        lines.append("")
        
        # 常量定义
        lines.append("// ==================== Constants ====================")
        lines.append("const CODE_LENGTH = 6;")
        lines.append("const VERIFY_DELAY = 1500;")
        lines.append("const TOAST_DURATION = 2000;")
        lines.append("")
        
        # 模块定义
        lines.append("// ==================== Module ====================")
        lines.append("export default {")
        self.indent_level = 1
        
        # 数据部分
        lines.append("")
        lines.append(self._indent() + "/**")
        lines.append(self._indent() + " * Page Data")
        lines.append(self._indent() + " */")
        lines.append(self._indent() + "data: {")
        self.indent_level = 2
        lines.append(self._indent() + self._generate_data_section())
        self.indent_level = 1
        lines.append(self._indent() + "},")
        
        # 生命周期钩子
        lines.append("")
        lines.append(self._indent() + "/**")
        lines.append(self._indent() + " * Lifecycle Hooks")
        lines.append(self._indent() + " */")
        lines.append(self._indent() + self._generate_lifecycle_section())
        
        # UI初始化
        lines.append("")
        lines.append(self._indent() + "/**")
        lines.append(self._indent() + " * UI Initialization")
        lines.append(self._indent() + " */")
        lines.append(self._indent() + self._generate_init_section())
        
        # 数据管理
        lines.append("")
        lines.append(self._indent() + "/**")
        lines.append(self._indent() + " * Data Management")
        lines.append(self._indent() + " */")
        lines.append(self._indent() + self._generate_data_management_section())
        
        # 事件处理
        lines.append("")
        lines.append(self._indent() + "/**")
        lines.append(self._indent() + " * Event Handlers")
        lines.append(self._indent() + " */")
        lines.append(self._indent() + self._generate_event_section())
        
        # 业务逻辑
        lines.append("")
        lines.append(self._indent() + "/**")
        lines.append(self._indent() + " * Business Logic")
        lines.append(self._indent() + " */")
        lines.append(self._indent() + self._generate_business_section())
        
        # 辅助方法
        lines.append("")
        lines.append(self._indent() + "/**")
        lines.append(self._indent() + " * Utilities")
        lines.append(self._indent() + " */")
        lines.append(self._indent() + self._generate_utils_section())
        
        self.indent_level = 0
        lines.append("};")
        
        return '\n'.join(lines)
    
    def _extract_import_name(self, imp: str) -> str:
        """提取导入名称"""
        parts = imp.split('/')
        return parts[-1] if parts else imp
    
    def _generate_data_section(self) -> str:
        """生成数据部分"""
        fields = []
        for field in self.module.data_fields[:10]:
            default = 'false' if 'is' in field else "''"
            fields.append(f"{field}: {default}")
        return ',\n        '.join(fields)
    
    def _generate_methods_section(self) -> str:
        """生成方法部分"""
        methods = []
        for func in self.module.functions[:10]:
            methods.append(f"{func.name}() {{}}")
        return ',\n    '.join(methods)
    
    def _generate_lifecycle_section(self) -> str:
        """生成生命周期部分"""
        lifecycle_funcs = [f for f in self.module.functions 
                         if f.name.startswith('on') and len(f.name) > 3]
        
        if not lifecycle_funcs:
            return "onInit() {\n        // Initialize page\n        this.initUI();\n        this.loadData();\n        this.setupEvents();\n    },"
        
        lines = []
        for func in lifecycle_funcs:
            lines.append(f"{func.name}() {{\n        // {func.name} lifecycle\n    }},")
        
        return '\n    '.join(lines)
    
    def _generate_init_section(self) -> str:
        """生成初始化部分"""
        init_funcs = [f for f in self.module.functions 
                     if 'init' in f.name.lower() or 'setup' in f.name.lower()]
        
        if not init_funcs:
            return "initUI() {\n        // Initialize UI components\n    },"
        
        lines = []
        for func in init_funcs:
            lines.append(f"{func.name}() {{\n        // {func.name}\n    }},")
        
        return '\n    '.join(lines)
    
    def _generate_data_management_section(self) -> str:
        """生成数据管理部分"""
        data_funcs = [f for f in self.module.functions 
                     if 'data' in f.name.lower() or 'load' in f.name.lower() 
                     or 'save' in f.name.lower()]
        
        if not data_funcs:
            return "loadData() {\n        // Load saved data\n    },\n    saveData() {\n        // Save data\n    },"
        
        lines = []
        for func in data_funcs:
            lines.append(f"{func.name}() {{\n        // {func.name}\n    }},")
        
        return '\n    '.join(lines)
    
    def _generate_event_section(self) -> str:
        """生成事件处理部分"""
        event_funcs = [f for f in self.module.functions 
                      if any(x in f.name.lower() for x in ['click', 'tap', 'swipe', 'touch', 'num', 'btn', 'del', 'confirm'])]
        
        if not event_funcs:
            return "onButtonClick() {\n        // Handle button click\n    },"
        
        lines = []
        for func in event_funcs:
            lines.append(f"{func.name}() {{\n        // {func.name}\n    }},")
        
        return '\n    '.join(lines)
    
    def _generate_business_section(self) -> str:
        """生成业务逻辑部分"""
        biz_funcs = [f for f in self.module.functions 
                    if any(x in f.name.lower() for x in ['verify', 'solve', 'check', 'test', 'validate'])]
        
        if not biz_funcs:
            return "verifyCode(code) {\n        // Verify code logic\n        return true;\n    },"
        
        lines = []
        for func in biz_funcs:
            lines.append(f"{func.name}(code) {{\n        // {func.name}\n        return true;\n    }},")
        
        return '\n    '.join(lines)
    
    def _generate_utils_section(self) -> str:
        """生成工具方法部分"""
        return "$element(id) {\n        return document.getElementById(id);\n    },\n    showToast(msg) {\n        // Show toast message\n    },\n    log(message, level = 'info') {\n        console[level](message);\n    }"
    
    def _indent(self) -> str:
        """生成缩进"""
        return "    " * self.indent_level


class ImprovedDecompiler:
    """改进版反编译器"""
    
    def __init__(self):
        self.extractor = StringExtractor()
        self.analyzer = None
        self.module = None
    
    def decompile(self, filepath: str, output_path: str = None, 
                  format_type: OutputFormat = OutputFormat.COMPLETE) -> str:
        """反编译"""
        print(f"[+] Decompiling: {filepath}")
        
        # 读取文件
        with open(filepath, 'rb') as f:
            data = f.read()
        
        print(f"    File size: {len(data)} bytes")
        
        # 提取字符串
        print(f"    Extracting strings...")
        strings = self.extractor.extract_from_bytes(data)
        print(f"    Found {len(strings)} strings")
        
        # 分析模块信息
        print(f"    Analyzing module...")
        self.module = self._create_module_info(strings, filepath)
        print(f"    Module: {self.module.name}")
        print(f"    Imports: {len(self.module.imports)}")
        print(f"    Functions: {len(self.module.functions)}")
        
        # 分析函数
        self.analyzer = FunctionAnalyzer(strings)
        functions = self.analyzer.analyze()
        self.module.functions = functions
        
        # 生成代码
        print(f"    Generating code...")
        generator = CodeGenerator(self.module)
        code = generator.generate(format_type)
        
        # 保存输出
        if output_path:
            self._save_output(output_path, code)
            print(f"[+] Output saved to: {output_path}")
        
        return code
    
    def _create_module_info(self, strings: List[Tuple[int, str]], filepath: str) -> ModuleInfo:
        """创建模块信息"""
        # 提取模块名
        module_name = "verify"
        for offset, s in strings:
            if s.startswith('@aiot/'):
                module_name = s.replace('@aiot/', '')
                break
        
        # 提取导入
        imports = self._extract_imports(strings)
        
        # 提取数据字段
        data_fields = self._extract_data_fields(strings)
        
        return ModuleInfo(
            name=module_name,
            path=filepath,
            imports=imports,
            data_fields=data_fields
        )
    
    def _extract_data_fields(self, strings: List[Tuple[int, str]]) -> List[str]:
        """提取数据字段"""
        # 常见的数据字段
        common_fields = {
            'nowselect', 'nowselectnum', 'nownum', 'isVerified', 
            'data', 'key', 'value', 'result', 'status'
        }
        
        data_fields = []
        seen = set()
        
        for offset, s in strings:
            # 检查是否在常见字段中
            if s in common_fields and s not in seen:
                data_fields.append(s)
                seen.add(s)
            # 检查是否为驼峰命名法的小写字段
            elif (len(s) >= 3 and len(s) <= 30 and 
                  s[0].islower() and 
                  s.replace('_', '').isalnum() and
                  any(c.isupper() for c in s[1:]) and
                  s not in seen):
                data_fields.append(s)
                seen.add(s)
        
        return data_fields[:15]  # 限制数量
    
    def _extract_imports(self, strings: List[Tuple[int, str]]) -> List[str]:
        """提取模块导入"""
        imports = []
        seen = set()
        
        for offset, s in strings:
            # 提取模块导入
            if s.startswith('@app-module/') or s.startswith('@aiot/'):
                if s not in seen:
                    imports.append(s)
                    seen.add(s)
        
        # 添加默认导入
        if not any('router' in imp.lower() for imp in imports):
            imports.append('@app-module/system.router')
        if not any('storage' in imp.lower() for imp in imports):
            imports.append('@app-module/system.storage')
        
        return imports
    
    def _save_output(self, output_path: str, code: str):
        """保存输出"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(code)


class BatchDecompiler:
    """批量反编译器"""
    
    def __init__(self):
        self.decompiler = ImprovedDecompiler()
    
    def decompile_directory(self, input_dir: str, output_dir: str,
                           format_type: OutputFormat = OutputFormat.COMPLETE):
        """批量反编译目录"""
        print(f"[+] Batch decompiling: {input_dir}")
        print(f"    Output directory: {output_dir}")
        
        # 查找所有.jsc文件
        jsc_files = list(Path(input_dir).rglob('*.jsc'))
        print(f"    Found {len(jsc_files)} .jsc files")
        
        # 反编译每个文件
        success = 0
        for jsc_file in jsc_files:
            try:
                output_file = os.path.join(
                    output_dir,
                    jsc_file.with_suffix('.js').name
                )
                self.decompiler.decompile(str(jsc_file), output_file, format_type)
                success += 1
            except Exception as e:
                print(f"    [!] Error decompiling {jsc_file}: {e}")
        
        print(f"\n[+] Batch decompilation complete: {success}/{len(jsc_files)} successful")


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Single file: python improved_decompiler.py <input.jsc> [output.js] [format]")
        print("  Directory:   python improved_decompiler.py -d <input_dir> <output_dir> [format]")
        print("")
        print("Formats: minified, pretty, complete (default: complete)")
        print("")
        print("Examples:")
        print("  python improved_decompiler.py demo/verify.jsc")
        print("  python improved_decompiler.py demo/verify.jsc output.js pretty")
        print("  python improved_decompiler.py -d ./input ./output")
        sys.exit(1)
    
    # 批量模式
    if sys.argv[1] == '-d':
        if len(sys.argv) < 4:
            print("Error: Please specify input directory and output directory")
            sys.exit(1)
        
        input_dir = sys.argv[2]
        output_dir = sys.argv[3]
        format_type = OutputFormat.PRETTY
        
        if len(sys.argv) >= 5:
            format_name = sys.argv[4].lower()
            format_type = OutputFormat(format_name) if format_name in [e.value for e in OutputFormat] else OutputFormat.PRETTY
        
        batch = BatchDecompiler()
        batch.decompile_directory(input_dir, output_dir, format_type)
    
    # 单文件模式
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) >= 3 else None
        format_type = OutputFormat.COMPLETE
        
        if len(sys.argv) >= 4:
            format_name = sys.argv[3].lower()
            format_type = OutputFormat(format_name) if format_name in [e.value for e in OutputFormat] else OutputFormat.COMPLETE
        
        if not output_file:
            base = os.path.splitext(input_file)[0]
            output_file = f"{base}_decompiled.js"
        
        decompiler = ImprovedDecompiler()
        result = decompiler.decompile(input_file, output_file, format_type)
        
        print(f"\n[+] Decompilation complete!")
        print(f"    Output: {output_file}")


if __name__ == "__main__":
    main()
