"""
MicroAgent v0.2 — Lightweight AI Agent for llama.cpp
Clean CLI with tools, memory, and auto-compaction.
"""

import requests
import json
import os
import sys
import subprocess
import re
import time
from datetime import datetime

# Enable ANSI colors on Windows
if sys.platform == "win32":
    os.system("")

# ── Config ───────────────────────────────────────────────────────────
BASE_URL = "http://localhost:8080"
MAX_TOKENS = 6000
COMPACT_AT = 4800
MAX_REPLY = 1024
TIMEOUT = 300
MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")
MAX_TOOL_ROUNDS = 5

# ── Rich Setup ───────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.text import Text
    from rich.rule import Rule
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.table import Table
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

if HAS_RICH:
    console = Console()
else:
    # Fallback plain console
    class FallbackConsole:
        def print(self, *args, **kwargs):
            text = " ".join(str(a) for a in args)
            print(text)
        def rule(self, title="", **kwargs):
            print(f"── {title} ──")
        def input(self, prompt=""):
            return input(prompt)
    console = FallbackConsole()

# ── Token Counting ───────────────────────────────────────────────────
def tok(text):
    return len(text) // 4

def msg_tokens(messages):
    return sum(tok(m["content"]) for m in messages)

# ── Memory ───────────────────────────────────────────────────────────
def load_mem():
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {"facts": []}

def save_mem(mem):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(mem, f, indent=2)
    except Exception as e:
        console.print(f"[red]Memory save error: {e}[/red]" if HAS_RICH else f"Memory save error: {e}")

# ── Tools ────────────────────────────────────────────────────────────
def t_read(args):
    try:
        with open(args.get("path",""), "r", encoding="utf-8", errors="replace") as f:
            c = f.read(8000)
        return c
    except Exception as e:
        return f"Error: {e}"

def t_write(args):
    p, c = args.get("path",""), args.get("content","")
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(c)
        return f"Written {len(c)} chars to {p}"
    except Exception as e:
        return f"Error: {e}"

def t_append(args):
    try:
        with open(args.get("path",""), "a", encoding="utf-8") as f:
            f.write(args.get("content",""))
        return "Done"
    except Exception as e:
        return f"Error: {e}"

def t_ls(args):
    p = args.get("path", ".")
    try:
        entries = []
        for e in sorted(os.listdir(p))[:50]:
            full = os.path.join(p, e)
            if os.path.isdir(full):
                entries.append(f"  [DIR]  {e}")
            else:
                entries.append(f"  {os.path.getsize(full):>8}  {e}")
        return "\n".join(entries) if entries else "(empty)"
    except Exception as e:
        return f"Error: {e}"

def t_cmd(args):
    cmd = args.get("command", "")
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        out = (r.stdout + r.stderr).strip()
        return out[:4000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Timed out (30s)"
    except Exception as e:
        return f"Error: {e}"

def t_remember(args, mem):
    f = args.get("fact", "")
    if f:
        mem["facts"].append(f)
        save_mem(mem)
        return f"Saved: {f}"
    return "No fact given"

def t_forget(args, mem):
    kw = args.get("keyword", "").lower()
    before = len(mem["facts"])
    mem["facts"] = [f for f in mem["facts"] if kw not in f.lower()]
    save_mem(mem)
    return f"Removed {before - len(mem['facts'])} entries"

TOOLS = {
    "file_read":   {"fn": t_read,   "info": "Read a file | args: path"},
    "file_write":  {"fn": t_write,  "info": "Write a file | args: path, content"},
    "file_append": {"fn": t_append, "info": "Append to file | args: path, content"},
    "list_files":  {"fn": t_ls,     "info": "List directory | args: path"},
    "run_command": {"fn": t_cmd,    "info": "Run shell cmd | args: command"},
    "remember":    {"fn": None,     "info": "Save to memory | args: fact"},
    "forget":      {"fn": None,     "info": "Forget by keyword | args: keyword"},
}

def run_tool(name, args, mem):
    if name == "remember": return t_remember(args, mem)
    if name == "forget":   return t_forget(args, mem)
    if name in TOOLS and TOOLS[name]["fn"]:
        return TOOLS[name]["fn"](args)
    return f"Unknown tool: {name}"

# ── System Prompt ────────────────────────────────────────────────────
def sys_prompt(mem):
    tlist = "\n".join(f"- {n}: {t['info']}" for n, t in TOOLS.items())
    mfacts = ""
    if mem["facts"]:
        mfacts = "\n\n## Memory\n" + "\n".join(f"- {f}" for f in mem["facts"][-25:])

    return f"""You are MicroAgent, a helpful AI assistant with tool access. Be concise.

## Tools
{tlist}

To use a tool:
<tool_call>
{{"name": "tool_name", "args": {{"key": "value"}}}}
</tool_call>

Only use tools when needed. Answer directly when you can.{mfacts}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M')} | CWD: {os.getcwd()}"""

# ── LLM Call ─────────────────────────────────────────────────────────
def llm_call(messages, stream=False):
    try:
        r = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            json={
                "model": "local",
                "messages": messages,
                "max_tokens": MAX_REPLY,
                "temperature": 1.0,
                "top_p": 0.95,
                "top_k": 64,
                "stream": False,
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except requests.ConnectionError:
        return "[ERROR] Cannot connect to llama-server. Is it running on port 8080?"
    except requests.Timeout:
        return "[ERROR] Request timed out."
    except Exception as e:
        return f"[ERROR] {e}"

# ── Parse Tool Calls ─────────────────────────────────────────────────
def parse_tools(text):
    matches = re.findall(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', text, re.DOTALL)
    calls = []
    for m in matches:
        try:
            p = json.loads(m)
            if "name" in p:
                calls.append(p)
        except:
            pass
    return calls

def strip_tools(text):
    return re.sub(r'<tool_call>.*?</tool_call>', '', text, flags=re.DOTALL).strip()

# ── Compaction ───────────────────────────────────────────────────────
def compact(messages):
    if len(messages) <= 5:
        return messages
    sys_msg = messages[0]
    recent = messages[-4:]
    old = messages[1:-4]
    if not old:
        return messages

    old_text = "\n".join(f"{m['role']}: {m['content'][:300]}" for m in old)[:3000]
    summary = llm_call([
        {"role": "system", "content": "Summarize briefly. Keep facts, paths, decisions."},
        {"role": "user", "content": old_text}
    ])
    return [sys_msg, {"role": "system", "content": f"[Summary]: {summary}"}] + recent

# ── Server Check ─────────────────────────────────────────────────────
def server_ok():
    try:
        return requests.get(f"{BASE_URL}/health", timeout=5).status_code == 200
    except:
        return False

# ── UI ───────────────────────────────────────────────────────────────
def show_banner():
    if HAS_RICH:
        banner = Text()
        banner.append("  ╔══════════════════════════════════════╗\n", style="cyan")
        banner.append("  ║", style="cyan")
        banner.append("      MicroAgent v0.2", style="bold white")
        banner.append("                 ║\n", style="cyan")
        banner.append("  ║", style="cyan")
        banner.append("  Lightweight AI • Tools • Memory", style="dim white")
        banner.append("     ║\n", style="cyan")
        banner.append("  ╚══════════════════════════════════════╝", style="cyan")
        console.print(banner)
        console.print(f"  Server: [cyan]localhost:8080[/cyan] │ Context: [cyan]6K[/cyan] │ /help", style="dim")
        console.print()
    else:
        print("\n  ╔══════════════════════════════════════╗")
        print("  ║      MicroAgent v0.2                 ║")
        print("  ║  Lightweight AI • Tools • Memory     ║")
        print("  ║  Made by Erik Boivin • Open Source   ║")
        print("  ╚══════════════════════════════════════╝")
        print("  Server: localhost:8080 │ Context: 6K │ /help\n")

def show_response(text):
    if HAS_RICH:
        try:
            console.print(Panel(
                Markdown(text),
                border_style="green",
                box=box.ROUNDED,
                padding=(1, 2),
            ))
        except:
            console.print(Panel(text, border_style="green", box=box.ROUNDED))
    else:
        print(f"\n{text}\n")

def show_tool(name, result):
    if HAS_RICH:
        console.print(f"  [yellow]⚡ {name}[/yellow]")
        console.print(Panel(
            result[:500],
            border_style="yellow",
            box=box.SIMPLE,
            padding=(0, 1),
        ))
    else:
        print(f"  [tool: {name}]")
        print(f"  {result[:500]}\n")

def show_thinking():
    if HAS_RICH:
        return Live(
            Spinner("dots", text="[dim] thinking...[/dim]", style="cyan"),
            console=console,
            transient=True,
        )
    else:
        print("  thinking...", end="\r")
        class FakeLive:
            def __enter__(self): return self
            def __exit__(self, *a): print("              ", end="\r")
        return FakeLive()

def show_status(messages):
    t = msg_tokens(messages)
    pct = min(int(t / MAX_TOKENS * 100), 100)
    filled = pct // 5
    bar = "█" * filled + "░" * (20 - filled)
    if HAS_RICH:
        console.print(f"  [dim]Context: {t}/{MAX_TOKENS} [{bar}] {pct}% │ Messages: {len(messages)}[/dim]\n")
    else:
        print(f"  Context: {t}/{MAX_TOKENS} [{bar}] {pct}% | Messages: {len(messages)}\n")

def show_help():
    if HAS_RICH:
        t = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        t.add_column(style="cyan bold")
        t.add_column(style="white")
        t.add_row("/help", "Show this help")
        t.add_row("/memory", "View saved memories")
        t.add_row("/clear", "Clear context, keep memory")
        t.add_row("/compact", "Force compaction now")
        t.add_row("/tokens", "Show context usage")
        t.add_row("/cd <path>", "Change working directory")
        t.add_row("/quit", "Exit")
        console.print(Panel(t, title="[bold]Commands[/bold]", border_style="cyan", box=box.ROUNDED))
    else:
        print("\n  /help     - Show this help")
        print("  /memory   - View saved memories")
        print("  /clear    - Clear context, keep memory")
        print("  /compact  - Force compaction now")
        print("  /tokens   - Show context usage")
        print("  /cd <path> - Change working directory")
        print("  /quit     - Exit\n")

def show_memory(mem):
    facts = mem.get("facts", [])
    if HAS_RICH:
        if facts:
            items = "\n".join(f"  [cyan]{i}.[/cyan] {f}" for i, f in enumerate(facts, 1))
            console.print(Panel(items, title=f"[bold]Memory ({len(facts)})[/bold]", border_style="cyan", box=box.ROUNDED))
        else:
            console.print("  [dim]No memories saved yet.[/dim]\n")
    else:
        if facts:
            for i, f in enumerate(facts, 1):
                print(f"  {i}. {f}")
        else:
            print("  No memories saved yet.")
        print()

# ── Main ─────────────────────────────────────────────────────────────
def main():
    show_banner()

    # Server check
    if not server_ok():
        if HAS_RICH:
            console.print("[red]  ✗ Cannot connect to llama-server on port 8080.[/red]")
            console.print("[dim]  Start the server first, then run this agent.[/dim]\n")
        else:
            print("  ERROR: Cannot connect to llama-server on port 8080.")
            print("  Start the server first, then run this agent.\n")
        input("  Press Enter to exit...")
        sys.exit(1)

    if HAS_RICH:
        console.print("[green]  ✓ Connected to llama-server[/green]\n")
    else:
        print("  Connected to llama-server\n")

    mem = load_mem()
    messages = [{"role": "system", "content": sys_prompt(mem)}]

    while True:
        # Input
        try:
            if HAS_RICH:
                user_input = console.input("[bold cyan]  ❯ [/bold cyan]").strip()
            else:
                user_input = input("  > ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n  [dim]Goodbye![/dim]" if HAS_RICH else "\n  Goodbye!")
            break

        if not user_input:
            continue

        # ── Commands ─────────────────────────────────────────────
        if user_input.startswith("/"):
            cmd = user_input.lower().split()[0]
            rest = user_input[len(cmd):].strip()

            if cmd in ("/quit", "/exit", "/q"):
                console.print("  [dim]Goodbye![/dim]" if HAS_RICH else "  Goodbye!")
                break
            elif cmd == "/help":
                show_help()
            elif cmd == "/memory":
                show_memory(mem)
            elif cmd == "/clear":
                messages = [{"role": "system", "content": sys_prompt(mem)}]
                console.print("  [dim]Context cleared.[/dim]\n" if HAS_RICH else "  Context cleared.\n")
            elif cmd == "/compact":
                messages = compact(messages)
                messages[0] = {"role": "system", "content": sys_prompt(mem)}
                show_status(messages)
            elif cmd == "/tokens":
                show_status(messages)
            elif cmd == "/cd":
                if rest:
                    try:
                        os.chdir(rest)
                        messages[0] = {"role": "system", "content": sys_prompt(mem)}
                        console.print(f"  [dim]→ {os.getcwd()}[/dim]\n" if HAS_RICH else f"  → {os.getcwd()}\n")
                    except Exception as e:
                        console.print(f"  [red]{e}[/red]\n" if HAS_RICH else f"  Error: {e}\n")
                else:
                    console.print(f"  [dim]{os.getcwd()}[/dim]\n" if HAS_RICH else f"  {os.getcwd()}\n")
            else:
                console.print("  [dim]Unknown command. /help[/dim]\n" if HAS_RICH else "  Unknown command. /help\n")
            continue

        # ── Add user message ─────────────────────────────────────
        messages.append({"role": "user", "content": user_input})

        # Auto-compact
        if msg_tokens(messages) > COMPACT_AT:
            if HAS_RICH:
                console.print("  [dim]Compacting context...[/dim]")
            else:
                print("  Compacting...")
            messages = compact(messages)
            messages[0] = {"role": "system", "content": sys_prompt(mem)}

        # ── Agent loop ───────────────────────────────────────────
        for rnd in range(MAX_TOOL_ROUNDS):
            with show_thinking():
                response = llm_call(messages)

            if response.startswith("[ERROR]"):
                if HAS_RICH:
                    console.print(f"  [red]{response}[/red]\n")
                else:
                    print(f"  {response}\n")
                break

            # Check for tools
            tool_calls = parse_tools(response)

            if not tool_calls:
                # Final response
                messages.append({"role": "assistant", "content": response})
                clean = strip_tools(response).strip()
                if clean:
                    show_response(clean)
                break

            # Execute tools
            messages.append({"role": "assistant", "content": response})
            for call in tool_calls:
                name = call.get("name", "?")
                args = call.get("args", {})
                result = run_tool(name, args, mem)
                show_tool(name, result)
                messages.append({"role": "user", "content": f"[Tool '{name}' result]:\n{result}"})

            if any(c.get("name") in ("remember", "forget") for c in tool_calls):
                messages[0] = {"role": "system", "content": sys_prompt(mem)}
        else:
            if HAS_RICH:
                console.print("  [dim]Max tool rounds reached.[/dim]\n")
            else:
                print("  Max tool rounds reached.\n")

if __name__ == "__main__":
    main()
