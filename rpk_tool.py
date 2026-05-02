#!/usr/bin/env python3
"""
RPK Tool - 小米手环 RPK 应用拆包与分析工具
"""

import argparse
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.tree import Tree
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

from unpacker import RPKUnpacker
from jsc_decompiler import JSCDecompiler
from ux_parser import UXParser
from js_beautifier import JSBeautifier
from manifest_parser import ManifestParser
from analyzer import RPKAnalyzer

console = Console()


def print_banner():
    banner = """
    ╔══════════════════════════════════════╗
    ║       RPK Tool v1.0                  ║
    ║   小米手环 RPK 拆包分析工具           ║
    ╚══════════════════════════════════════╝
    """
    console.print(Panel(banner, style="bold cyan"))


def cmd_unpack(args):
    """解包 RPK 文件"""
    unpacker = RPKUnpacker(args.input)

    if not unpacker.validate():
        console.print("[red]错误: 无效的 RPK 文件[/red]")
        return

    console.print(f"[green]正在解包: {args.input}[/green]")

    output_dir = args.output or args.input.replace('.rpk', '_unpacked')
    result = unpacker.unpack(output_dir)

    console.print(f"[green]解包完成: {output_dir}[/green]")
    console.print(f"文件数量: {result['file_count']}")

    # 显示目录结构
    tree = Tree(f"📁 {os.path.basename(output_dir)}")
    _build_tree(tree, output_dir)
    console.print(tree)


def cmd_decompile(args):
    """反编译 RPK 中的 .jsc 文件"""
    input_path = Path(args.input)

    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        files = list(input_path.rglob("*.jsc"))
    else:
        console.print("[red]错误: 无效的路径[/red]")
        return

    if not files:
        console.print("[yellow]未找到 .jsc 文件[/yellow]")
        return

    decompiler = JSCDecompiler()
    output_dir = args.output or str(input_path.parent / "decompiled")

    os.makedirs(output_dir, exist_ok=True)

    for jsc_file in files:
        console.print(f"[cyan]反编译: {jsc_file.name}[/cyan]")
        try:
            result = decompiler.decompile(str(jsc_file))
            if result:
                out_path = os.path.join(
                    output_dir,
                    jsc_file.stem + ".js"
                )
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(result)
                console.print(f"  [green]✓ 输出: {out_path}[/green]")
            else:
                console.print(f"  [yellow]⚠ 无法反编译（未知字节码格式）[/yellow]")
        except Exception as e:
            console.print(f"  [red]✗ 失败: {e}[/red]")

    console.print(f"\n[green]反编译完成，输出目录: {output_dir}[/green]")


def cmd_beautify(args):
    """美化 JS 文件"""
    beautifier = JSBeautifier()
    input_path = Path(args.input)

    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        files = list(input_path.rglob("*.js"))
    else:
        console.print("[red]错误: 无效的路径[/red]")
        return

    for js_file in files:
        console.print(f"[cyan]美化: {js_file.name}[/cyan]")
        try:
            beautifier.beautify_file(str(js_file))
            console.print(f"  [green]✓ 完成[/green]")
        except Exception as e:
            console.print(f"  [red]✗ 失败: {e}[/red]")


def cmd_parse_ux(args):
    """解析 .ux 文件，拆分为 .js / .xml / .css"""
    parser = UXParser()
    input_path = Path(args.input)

    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        files = list(input_path.rglob("*.ux"))
    else:
        console.print("[red]错误: 无效的路径[/red]")
        return

    if not files:
        console.print("[yellow]未找到 .ux 文件[/yellow]")
        return

    output_dir = args.output or str(input_path.parent / "ux_split")
    os.makedirs(output_dir, exist_ok=True)

    for ux_file in files:
        console.print(f"[cyan]解析: {ux_file.name}[/cyan]")
        try:
            result = parser.split(str(ux_file), output_dir)
            for part, path in result.items():
                console.print(f"  [green]✓ {part}: {path}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ 失败: {e}[/red]")


def cmd_merge_ux(args):
    """将分离的 .js/.xml/.css 合并为 .ux"""
    parser = UXParser()
    input_path = Path(args.input)

    output_dir = args.output or str(input_path.parent / "ux_merged")
    os.makedirs(output_dir, exist_ok=True)

    console.print(f"[cyan]扫描目录: {input_path}[/cyan]")
    groups = parser.find_groups(str(input_path))

    if not groups:
        console.print("[yellow]未找到可合并的文件组[/yellow]")
        return

    for group in groups:
        console.print(f"[cyan]合并: {group['name']}[/cyan]")
        result = parser.merge(group, output_dir)
        console.print(f"  [green]✓ 输出: {result}[/green]")


def cmd_info(args):
    """显示 RPK 包详细信息"""
    unpacker = RPKUnpacker(args.input)

    if not unpacker.validate():
        console.print("[red]错误: 无效的 RPK 文件[/red]")
        return

    # 基本信息
    file_size = os.path.getsize(args.input)
    console.print(Panel(
        f"文件: {args.input}\n"
        f"大小: {file_size:,} 字节 ({file_size/1024:.1f} KB)",
        title="RPK 文件信息",
        style="cyan"
    ))

    # 解析 manifest
    manifest = ManifestParser()
    info = manifest.parse_rpk(args.input)

    if info:
        table = Table(title="应用信息")
        table.add_column("字段", style="cyan")
        table.add_column("值", style="white")

        fields = {
            "包名": info.get("package", "N/A"),
            "名称": info.get("name", "N/A"),
            "版本": info.get("versionName", "N/A"),
            "版本号": str(info.get("versionCode", "N/A")),
            "最低平台": str(info.get("minPlatformVersion", "N/A")),
            "图标": info.get("icon", "N/A"),
        }

        for key, value in fields.items():
            table.add_row(key, value)

        console.print(table)

        # 功能特性
        features = info.get("features", [])
        if features:
            console.print("\n[bold]声明的功能:[/bold]")
            for f in features:
                console.print(f"  • {f.get('name', 'unknown')}")

        # 页面路由
        router = info.get("router", {})
        pages = router.get("pages", {})
        if pages:
            console.print("\n[bold]页面路由:[/bold]")
            for page, config in pages.items():
                console.print(f"  • {page} -> {config.get('component', '?')}")

    # 文件统计
    analyzer = RPKAnalyzer()
    stats = analyzer.analyze_rpk(args.input)

    if stats:
        table = Table(title="文件统计")
        table.add_column("类型", style="cyan")
        table.add_column("数量", justify="right")
        table.add_column("大小", justify="right")

        for ext, data in sorted(stats.items()):
            table.add_row(ext, str(data['count']),
                          f"{data['size']:,} B")

        console.print(table)


def cmd_analyze(args):
    """深度静态分析 RPK"""
    analyzer = RPKAnalyzer()
    console.print(f"[cyan]正在分析: {args.input}[/cyan]\n")

    report = analyzer.full_analysis(args.input)

    # API 调用统计
    if report.get('api_calls'):
        console.print("[bold]API 调用:[/bold]")
        for api, count in report['api_calls'].most_common(20):
            console.print(f"  {api}: {count} 次")

    # 字符串提取
    if report.get('strings'):
        console.print(f"\n[bold]关键字符串 (前 30 个):[/bold]")
        for s in report['strings'][:30]:
            console.print(f"  \"{s}\"")

    # 网络端点
    if report.get('urls'):
        console.print(f"\n[bold]网络端点:[/bold]")
        for url in report['urls']:
            console.print(f"  {url}")

    # 硬编码值
    if report.get('hardcoded'):
        console.print(f"\n[bold]硬编码配置:[/bold]")
        for key, value in report['hardcoded'].items():
            console.print(f"  {key} = {value}")


def _build_tree(tree, path, depth=0, max_depth=3):
    """递归构建目录树"""
    if depth >= max_depth:
        return

    try:
        entries = sorted(os.listdir(path))
    except PermissionError:
        return

    dirs = [e for e in entries if os.path.isdir(os.path.join(path, e))]
    files = [e for e in entries if os.path.isfile(os.path.join(path, e))]

    for d in dirs[:20]:
        branch = tree.add(f"📁 {d}")
        _build_tree(branch, os.path.join(path, d), depth + 1, max_depth)

    for f in files[:30]:
        size = os.path.getsize(os.path.join(path, f))
        ext = os.path.splitext(f)[1]

        if ext in ('.js', '.jsc'):
            style = "yellow"
        elif ext in ('.xml', '.ux'):
            style = "green"
        elif ext in ('.json',):
            style = "cyan"
        elif ext in ('.png', '.jpg', '.gif'):
            style = "magenta"
        else:
            style = "white"

        tree.add(f"[{style}]{f}[/{style}] ({size:,} B)")

    remaining_files = len(files) - 30
    if remaining_files > 0:
        tree.add(f"[dim]... 还有 {remaining_files} 个文件[/dim]")


def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="RPK Tool - 小米手环 RPK 应用拆包分析工具"
    )
    subparsers = parser.add_subparsers(dest='command')

    # unpack 命令
    p_unpack = subparsers.add_parser('unpack', help='解包 RPK 文件')
    p_unpack.add_argument('input', help='RPK 文件路径')
    p_unpack.add_argument('-o', '--output', help='输出目录')

    # decompile 命令
    p_decompile = subparsers.add_parser('decompile', help='反编译 .jsc 文件')
    p_decompile.add_argument('input', help='.jsc 文件或包含 .jsc 的目录')
    p_decompile.add_argument('-o', '--output', help='输出目录')

    # beautify 命令
    p_beautify = subparsers.add_parser('beautify', help='美化 JS 文件')
    p_beautify.add_argument('input', help='JS 文件或目录')

    # ux 命令组
    p_ux = subparsers.add_parser('ux', help='.ux 文件操作')
    ux_sub = p_ux.add_subparsers(dest='ux_command')

    p_ux_split = ux_sub.add_parser('split', help='拆分 .ux 为 .js/.xml/.css')
    p_ux_split.add_argument('input', help='.ux 文件或目录')
    p_ux_split.add_argument('-o', '--output', help='输出目录')

    p_ux_merge = ux_sub.add_parser('merge', help='合并 .js/.xml/.css 为 .ux')
    p_ux_merge.add_argument('input', help='包含分离文件的目录')
    p_ux_merge.add_argument('-o', '--output', help='输出目录')

    # info 命令
    p_info = subparsers.add_parser('info', help='查看 RPK 包信息')
    p_info.add_argument('input', help='RPK 文件路径')

    # analyze 命令
    p_analyze = subparsers.add_parser('analyze', help='深度静态分析')
    p_analyze.add_argument('input', help='RPK 文件或解包目录')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        'unpack': cmd_unpack,
        'decompile': cmd_decompile,
        'beautify': cmd_beautify,
        'info': cmd_info,
        'analyze': cmd_analyze,
    }

    if args.command == 'ux':
        ux_commands = {
            'split': cmd_parse_ux,
            'merge': cmd_merge_ux,
        }
        if args.ux_command in ux_commands:
            ux_commands[args.ux_command](args)
        else:
            p_ux.print_help()
    elif args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
