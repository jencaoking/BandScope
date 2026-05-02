# BandScope

RPK 应用拆包与分析工具 - 小米手环应用逆向工程工具集

## 项目简介

BandScope 是一款专为小米手环 RPK 应用设计的逆向工程工具集，提供完整的拆包、反编译、静态分析和代码美化功能。支持多种字节码格式的反编译，包括 V8 Snapshot、QuickJS 和 JerryScript。

## 功能特性

- **RPK 解包** - 完整的 RPK 应用包解包功能
- **JSC 反编译** - 支持 V8 Snapshot、V8 Code Cache、QuickJS、JerryScript 字节码
- **UX 解析** - `.ux` 单文件组件的拆分与合并
- **JS 美化** - 代码格式化与美化
- **静态分析** - API 调用统计、敏感信息检测、硬编码值提取
- **Manifest 解析** - 应用配置信息提取

## 目录结构

```
BandScope/
├── analyzer.py          # RPK 静态分析模块
├── js_beautifier.py     # JS 代码美化
├── jsc_decompiler.py    # JSC 字节码反编译器
├── manifest_parser.py   # manifest.json 解析器
├── rpk_tool.py          # 主程序 CLI 入口
├── ux_parser.py         # UX 文件解析器
├── unpacker.py          # RPK 解包模块
├── requirements.txt     # 依赖列表
└── README.md            # 项目文档
```

## 快速开始

### 环境要求

- Python 3.8+
- Node.js（用于部分字节码反编译）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 基本使用

```bash
# 解包 RPK 文件
python rpk_tool.py unpack input.rpk -o output_dir

# 反编译 JSC 字节码
python rpk_tool.py decompile input.jsc -o output_dir

# 解析 UX 文件
python rpk_tool.py parse-ux input.ux -o output_dir

# 美化 JS 文件
python rpk_tool.py beautify input.js

# 查看 RPK 应用信息
python rpk_tool.py info input.rpk

# 完整静态分析
python rpk_tool.py analyze input.rpk
```

## 核心模块

### RPKUnpacker

RPK 文件解包器，支持验证、解包、文件列表读取。

```python
from unpacker import RPKUnpacker

unpacker = RPKUnpacker("app.rpk")
if unpacker.validate():
    result = unpacker.unpack("output_dir")
    print(f"解包成功: {result['file_count']} 个文件")
```

### JSCDecompiler

JSC 字节码反编译器，自动检测字节码类型并反编译。

```python
from jsc_decompiler import JSCDecompiler

decompiler = JSCDecompiler()
result = decompiler.decompile("bytecode.jsc")
```

### UXParser

UX 单文件组件解析器，支持拆分与合并。

```python
from ux_parser import UXParser

parser = UXParser()
# 拆分
parser.split("component.ux", "output_dir")
# 合并
parser.merge({"name": "comp", "js": "a.js", "xml": "b.xml"}, "output_dir")
```

### RPKAnalyzer

RPK 静态分析器，提取 API 调用、URL、敏感信息等。

```python
from analyzer import RPKAnalyzer

analyzer = RPKAnalyzer()
report = analyzer.full_analysis("input.rpk")
print(f"API 调用: {report['api_calls']}")
print(f"URL 列表: {report['urls']}")
```

## 依赖

- `jsbeautifier>=1.14.0` - JS 代码美化
- `pyperclip>=1.8.2` - 剪贴板操作
- `rich>=13.0.0` - 富文本终端输出
- `lark>=1.1.0` - 语法解析

## 许可证

本项目基于 Apache License 2.0协议开源。

## 免责声明

本工具仅供学习和研究使用。请勿将本工具用于任何商业或非法目的。使用本工具即表示您同意承担所有责任。
