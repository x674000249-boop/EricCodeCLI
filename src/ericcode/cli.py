"""
EricCode CLI - 命令行接口

提供用户友好的命令行界面，支持多种交互模式：
- 单命令模式：一次性执行任务
- 交互式REPL：持续对话
- TUI界面：丰富的终端UI体验
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ericcode import APP_NAME, VERSION

app = typer.Typer(
    name="ericcode",
    help=Text("🤖 ").append(APP_NAME, style="bold blue").append(" - AI驱动的智能编码助手").markup,
    no_args_is_help=True,
    rich_markup_mode="rich",
    add_completion=True,
)

console = Console()


@app.command()
def version():
    """显示版本信息"""
    from ericcode import __github__
    console.print(Panel(
        f"[bold green]{APP_NAME}[/]\n"
        f"版本: [cyan]{VERSION}[/]\n"
        f"Python: {'.'.join(map(str, __import__('sys').version_info[:3]))}\n"
        f"作者: [cyan]NoWint[/]\n"
        f"GitHub: [cyan]{__github__}[/]",
        title=f"🚀 {APP_NAME}",
        border_style="green",
    ))


@app.command()
def generate(
    prompt: str = typer.Argument(..., help="[bold cyan]自然语言描述[/]，例如：'创建一个RESTful API的用户认证模块'"),
    lang: str = typer.Option(None, "--lang", "-l", help="目标编程语言 (python/javascript/java/go/rust/c++等)"),
    output: str = typer.Option(None, "--output", "-o", help="输出文件路径"),
    context: str = typer.Option(None, "--context", "-c", help="上下文文件或目录路径"),
    framework: str = typer.Option(None, "--framework", "-f", help="指定框架 (fastapi/flask/django/express等)"),
    model: str = typer.Option(None, "--model", "-m", help="指定使用的模型 (gpt-4o/gpt-4o-mini/local等)"),
    temperature: float = typer.Option(0.7, "--temperature", "-t", min=0.0, max=2.0, help="创造性参数 (0.0-2.0)"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="交互式模式"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出模式"),
):
    """✨ 基于自然语言描述生成代码"""
    from ericcode.core.generator import CodeGenerator
    
    with console.status("[bold green]正在生成代码...", spinner="dots"):
        generator = CodeGenerator()
        
        options = {
            "language": lang,
            "framework": framework,
            "model": model,
            "temperature": temperature,
            "context_path": context,
            "output_path": output,
        }
        
        try:
            result = generator.generate(prompt, **{k: v for k, v in options.items() if v is not None})
            
            console.print(Panel(
                f"[bold green]✅ 生成成功！[/]\n\n"
                f"[dim]语言:[/] {result.language or '自动检测'}\n"
                f"[dim]模型:[/] {result.model_used}\n"
                f"[dim]耗时:[/] {result.latency_ms:.2f}ms\n"
                f"[dim]置信度:[/] {result.confidence:.1%}",
                title="📊 生成结果",
                border_style="green",
            ))
            
            if output:
                console.print(f"\n[green]💾 代码已保存到: [/]{output}")
            
            console.print(f"\n[bold]生成的代码:[/]")
            from pygments import highlight
            from pygments.lexers import get_lexer_by_name, guess_lexer
            from pygments.formatters import Terminal256Formatter
            
            try:
                lexer = get_lexer_by_name(result.language or "python") if result.language else guess_lexer(result.code)
            except Exception:
                from pygments.lexers import TextLexer
                lexer = TextLexer()
            
            highlighted = highlight(result.code, lexer, Terminal256Formatter(style='monokai'))
            console.print(highlighted)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️ 用户取消操作[/]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"\n[red]❌ 生成失败: [/]{str(e)}")
            raise typer.Exit(1)


@app.command()
def complete(
    file: str = typer.Argument(..., help="要补全的代码文件路径"),
    line: int = typer.Option(None, "--line", "-l", help="光标所在行号（从1开始）"),
    column: int = typer.Option(None, "--column", "-c", help="光标所在列号（从1开始）"),
    watch: bool = typer.Option(False, "--watch", "-w", help="持续监听模式"),
):
    """💡 智能代码补全"""
    from ericcode.core.completer import CodeCompleter
    
    completer = CodeCompleter(watch_mode=watch)
    
    if watch:
        console.print("[bold cyan]👁️  监听模式启动... 按 Ctrl+C 退出[/]")
    
    try:
        suggestions = completer.get_suggestions(file, line=line, column=column)
        
        if suggestions:
            console.print(f"\n[bold green]✨ 发现 {len(suggestions)} 个补全建议:[/]\n")
            for i, suggestion in enumerate(suggestions, 1):
                confidence_bar = "█" * int(suggestion.confidence * 10) + "░" * (10 - int(suggestion.confidence * 10))
                console.print(
                    f"  [cyan]{i}.[/] {suggestion.text[:60]}{'...' if len(suggestion.text) > 60 else ''}\n"
                    f"     [dim]{confidence_bar}[/] [green]{suggestion.confidence:.0%}[/]"
                )
        else:
            console.print("[yellow]💭 没有找到合适的补全建议[/]")
            
    except FileNotFoundError:
        console.print(f"[red]❌ 文件不存在: [/]{file}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]❌ 补全失败: [/]{str(e)}")
        raise typer.Exit(1)


@app.command()
def explain(
    file_path: str = typer.Argument(..., help="[bold cyan]要解释的代码文件[/]路径"),
    level: str = typer.Option(
        "summary",
        "--level",
        "-l",
        help="解释深度: [bold]summary[/](概述) / [bold]detailed[/](详细) / [bold]tutorial[/](教学)"
    ),
    language: str = typer.Option("zh", "--language", "--lang", help="输出语言: zh/en/both"),
    output_format: str = typer.Option(
        "text",
        "--format",
        "-f",
        help="输出格式: text/markdown/json"
    ),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="交互式探索模式"),
    lines: str = typer.Option(None, "--lines", "-r", help="指定行范围，例如: '1-50' 或 '30-'"),
):
    """📖 详细解释代码功能和逻辑"""
    from ericcode.core.explainer import CodeExplainer
    
    with console.status("[bold green]正在分析代码...", spinner="dots12"):
        explainer = CodeExplainer()
        
        try:
            # 解析行范围
            line_range = None
            if lines:
                parts = lines.split("-")
                start = int(parts[0]) if parts[0] else None
                end = int(parts[1]) if len(parts) > 1 and parts[1] else None
                line_range = (start, end)
            
            explanation = explainer.explain(
                file_path=file_path,
                level=level,
                target_language=language,
                interactive=interactive,
                line_range=line_range,
            )
            
            # 根据输出格式展示结果
            if output_format == "json":
                import json
                console.print_json(json.dumps(explanation.to_dict(), indent=2, ensure_ascii=False))
            elif output_format == "markdown":
                console.print(explanation.to_markdown())
            else:
                console.print(explanation.to_rich_panel())
                
        except FileNotFoundError:
            console.print(f"[red]❌ 文件不存在: [/]{file_path}")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]❌ 解释失败: [/]{str(e)}")
            if "--verbose" in str(sys.argv):  # 简单检查
                import traceback
                console.print(traceback.format_exc())
            raise typer.Exit(1)


@app.command()
def chat():
    """💬 启动交互式对话模式"""
    from ericcode.core.chat import start_chat
    
    console.print(Panel(
        "[bold green]欢迎来到 EricCode 对话模式！[/]\n\n"
        "输入你的问题或需求，输入 [bold yellow]exit[/] 或 [bold yellow]quit[/] 退出\n"
        "输入 [bold cyan]/help[/] 查看更多命令\n"
        "输入 [bold cyan]/clear[/] 清除对话历史",
        title="💬 EricCode Chat",
        border_style="blue",
    ))
    
    start_chat()


@app.command()
def shell_wizard(
    prompt: str = typer.Argument(..., help="自然语言描述，例如：'查找并删除当前目录大于100M的文件'"),
    shell: str = typer.Option("bash", "--shell", "-s", help="Shell类型 (bash/zsh/powershell)"),
    explain: bool = typer.Option(True, "--explain", "-e", help="生成命令解释"),
    safe_mode: bool = typer.Option(True, "--safe", "-S", help="启用安全检查"),
):
    """⚡ 自然语言转Shell命令"""
    from ericcode.core.shell_wizard import generate_shell_command
    
    with console.status("[bold green]正在生成Shell命令...", spinner="dots"):
        try:
            result = generate_shell_command(prompt, shell, explain, safe_mode)
            
            console.print(Panel(
                f"[bold green]✅ 生成成功！[/]\n\n"
                f"[dim]Shell类型:[/] {result.shell_type}\n"
                f"[dim]安全性:[/] {'安全' if result.is_safe else '可能危险'}\n",
                title="📊 生成结果",
                border_style="green",
            ))
            
            console.print(f"\n[bold]生成的命令:[/]")
            console.print(f"[cyan]{result.command}[/]")
            
            if result.explanation:
                console.print(f"\n[bold]命令解释:[/]")
                console.print(result.explanation)
                
        except Exception as e:
            console.print(f"\n[red]❌ 生成失败: [/]{str(e)}")
            raise typer.Exit(1)


@app.command()
def secret_scrubber(
    input_file: str = typer.Argument(None, help="输入文件路径，不指定则从标准输入读取"),
    output_file: str = typer.Option(None, "--output", "-o", help="输出文件路径，不指定则输出到标准输出"),
    rules: str = typer.Option(None, "--rules", "-r", help="要应用的规则，逗号分隔，例如：'api_key,password,ip_address'"),
):
    """🔒 自动识别并抹除敏感信息"""
    from ericcode.core.secret_scrubber import scrub_text, scrub_file
    import sys
    
    try:
        if input_file:
            # 从文件读取
            result = scrub_file(input_file, output_file, rules.split(",") if rules else None)
            console.print(f"[green]✅ 处理完成！[/] 检测到 {result.scrub_count} 个敏感信息")
        else:
            # 从标准输入读取
            text = sys.stdin.read()
            result = scrub_text(text, rules.split(",") if rules else None)
            
            if output_file:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(result.scrubbed_text)
                console.print(f"[green]✅ 处理完成！[/] 检测到 {result.scrub_count} 个敏感信息，已保存到 {output_file}")
            else:
                console.print(result.scrubbed_text)
                console.print(f"\n[green]✅ 处理完成！[/] 检测到 {result.scrub_count} 个敏感信息")
                
    except Exception as e:
        console.print(f"\n[red]❌ 处理失败: [/]{str(e)}")
        raise typer.Exit(1)


@app.command()
def git_smart_commit(
    message: str = typer.Option(None, "--message", "-m", help="提交信息前缀"),
    repo_path: str = typer.Option(None, "--repo", "-r", help="Git仓库路径"),
    range_: str = typer.Option(None, "--range", "-R", help="提交范围，例如：'HEAD~1..HEAD'"),
):
    """💡 智能Git提交信息生成"""
    from ericcode.core.git_smart_commit import commit
    
    with console.status("[bold green]正在分析变更并生成提交信息...", spinner="dots"):
        try:
            success = commit(message, repo_path, range_)
            if success:
                console.print("[green]✅ 提交成功！[/]")
            else:
                console.print("[red]❌ 提交失败！[/]")
                raise typer.Exit(1)
                
        except Exception as e:
            console.print(f"\n[red]❌ 生成失败: [/]{str(e)}")
            raise typer.Exit(1)


@app.command()
def format_shifter(
    input_file: str = typer.Argument(None, help="输入文件路径，不指定则从标准输入读取"),
    output_file: str = typer.Option(None, "--output", "-o", help="输出文件路径，不指定则输出到标准输出"),
    output_format: str = typer.Option(..., "--format", "-f", help="输出格式 (json/yaml/csv/markdown/text)"),
    input_format: str = typer.Option(None, "--input-format", "-i", help="输入格式，不指定则自动检测"),
):
    """🔄 智能格式转换"""
    from ericcode.core.format_shifter import convert_text, convert_file
    import sys
    import asyncio
    
    async def run_conversion():
        try:
            if input_file:
                # 从文件读取
                result = await convert_file(input_file, output_file, output_format, input_format)
            else:
                # 从标准输入读取
                text = sys.stdin.read()
                result = await convert_text(text, output_format, input_format)
            
            if result.success:
                if output_file:
                    console.print(f"[green]✅ 转换完成！[/] 已保存到 {output_file}")
                else:
                    console.print(result.converted_text)
            else:
                console.print(f"[red]❌ 转换失败: [/]{result.error_message}")
                raise typer.Exit(1)
                
        except Exception as e:
            console.print(f"\n[red]❌ 转换失败: [/]{str(e)}")
            raise typer.Exit(1)
    
    asyncio.run(run_conversion())


@app.command()
def dungeon_cli(
    player_name: str = typer.Option(None, "--name", "-n", help="玩家名称"),
    load: bool = typer.Option(False, "--load", "-l", help="加载保存的游戏"),
):
    """🎮 终端文字冒险游戏"""
    from ericcode.core.dungeon_cli import start_game, load_saved_game
    import asyncio
    
    async def run_game():
        try:
            local_player_name = player_name
            
            if load:
                # 加载游戏
                game = load_saved_game()
                if not game:
                    console.print("[yellow]⚠️  没有找到保存的游戏，开始新游戏[/]")
                    if not local_player_name:
                        local_player_name = input("请输入玩家名称: ")
                    game = start_game(local_player_name)
            else:
                # 开始新游戏
                if not local_player_name:
                    local_player_name = input("请输入玩家名称: ")
                game = start_game(local_player_name)
            
            # 显示游戏状态
            console.print(game.get_game_status())
            
            # 游戏主循环
            while True:
                action = input("\n输入你的动作: ")
                if action.lower() in ["exit", "quit", "退出"]:
                    console.print(game.quit_game())
                    break
                elif action.lower() in ["status", "状态"]:
                    console.print(game.get_game_status())
                else:
                    result = await game.process_action(action)
                    console.print(f"\n{result}")
                    
        except Exception as e:
            console.print(f"\n[red]❌ 游戏失败: [/]{str(e)}")
            raise typer.Exit(1)
    
    asyncio.run(run_game())


@app.command()
def lm_studio(
    action: str = typer.Argument(..., help="操作 (open/status/config)"),
):
    """🧠 LM Studio管理"""
    from ericcode.providers.lm_studio import get_lm_studio_integration
    
    integration = get_lm_studio_integration()
    
    if action == "open":
        # 打开LM Studio
        with console.status("[bold green]正在打开LM Studio...", spinner="dots"):
            success = integration.open_lm_studio()
            if success:
                console.print("[green]✅ LM Studio已打开！[/]")
                console.print("[dim]请在LM Studio中加载模型并启用OpenAI兼容API[/]")
            else:
                console.print("[red]❌ 打开LM Studio失败！[/]")
                raise typer.Exit(1)
    
    elif action == "status":
        # 检查LM Studio状态
        with console.status("[bold green]正在检查LM Studio状态...", spinner="dots"):
            status = integration.check_status()
            
            if status.is_running:
                console.print(Panel(
                    f"[bold green]✅ LM Studio正在运行！[/]\n\n"
                    f"[dim]API端点:[/] {status.api_endpoint}\n"
                    f"[dim]API密钥:[/] {status.api_key}\n"
                    f"[dim]当前模型:[/] {status.model or '未加载'}\n"
                    f"[dim]版本:[/] {status.version or '未知'}",
                    title="📊 LM Studio状态",
                    border_style="green",
                ))
            else:
                console.print(Panel(
                    "[bold red]❌ LM Studio未运行[/]\n\n"
                    "请先启动LM Studio并启用OpenAI兼容API\n"
                    "你可以使用 `ericcode lm-studio open` 命令打开LM Studio",
                    title="📊 LM Studio状态",
                    border_style="red",
                ))
    
    elif action == "config":
        # 显示API配置
        config = integration.get_api_config()
        console.print(Panel(
            f"[bold blue]LM Studio API配置[/]\n\n"
            f"[dim]API密钥:[/] {config['api_key']}\n"
            f"[dim]API端点:[/] {config['base_url']}\n"
            f"[dim]默认模型:[/] {config['default_model']}\n\n"
            "[dim]你可以将这些配置添加到.env文件中:[/]\n"
            f"ERICCODE_OPENAI_API_KEY={config['api_key']}\n"
            f"ERICCODE_OPENAI_BASE_URL={config['base_url']}\n"
            f"ERICCODE_OPENAI_DEFAULT_MODEL={config['default_model']}",
            title="⚙️ LM Studio配置",
            border_style="blue",
        ))
    
    else:
        console.print(f"[red]❌ 无效的操作: [/]{action}")
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="启用详细日志输出"),
    config_file: str = typer.Option(None, "--config", "-c", help="指定配置文件路径"),
    no_color: bool = typer.Option(False, "--no-color", help="禁用彩色输出"),
):
    """
    🤖 [bold blue]EricCode[/] - AI驱动的智能编码助手
    
    支持中英文双语交互，让编码更智能、更高效！
    """
    if ctx.invoked_subcommand is None:
        console.print(Panel(
            f"[bold green]{APP_NAME}[/] v[blue]{VERSION}[/]\n\n"
            "[bold]常用命令:[/]\n"
            "  [cyan]generate[/]       - ✨ 生成代码\n"
            "  [cyan]complete[/]       - 💡 代码补全\n"
            "  [cyan]explain[/]        - 📖 代码解释\n"
            "  [cyan]chat[/]           - 💬 对话模式\n"
            "  [cyan]shell-wizard[/]   - ⚡ 自然语言转Shell命令\n"
            "  [cyan]secret-scrubber[/] - 🔒 敏感信息清洗\n"
            "  [cyan]git-smart-commit[/] - 💡 智能Git提交信息\n"
            "  [cyan]format-shifter[/]  - 🔄 格式转换\n"
            "  [cyan]dungeon-cli[/]     - 🎮 文字冒险游戏\n"
            "  [cyan]lm-studio[/]      - 🧠 LM Studio管理\n"
            "  [cyan]version[/]        - 🔢 版本信息\n\n"
            "[dim]使用 --help 查看每个命令的详细帮助[/]",
            title=f"🚀 {APP_NAME}",
            border_style="green",
        ))


if __name__ == "__main__":
    app()
