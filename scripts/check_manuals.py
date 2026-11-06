"""Claude Code hook (PreToolUse, Bash): keep the user manuals in step with the screens.

Before a `git commit`, if the staged files change what users see (templates, static
files, texts) and the manuals (docs/manuales/*.pdf) aren't staged too, the commit is
blocked (exit 2) with what to do: run scripts/make_manuals.py, check the cuts, stage
the PDFs. A change that doesn't touch any screen the manuals show can say so with
"[manuals: n/a]" in the commit message.

Standard library only. Reads the hook's JSON on stdin; see .claude/settings.json.
"""
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# What users see: pages, styles, scripts, images, texts. Not the manuals themselves.
UX = re.compile(r"^(app/templates/|app/static/(?!manuals/)|app/i18n\.py$)")
MANUALS = ("docs/manuales/", "app/static/manuals/")
SKIP = "[manuals: n/a]"


def message(command):
    """The commit message: -m values and the contents of -F files."""
    try:
        words = shlex.split(command, posix=True)
    except ValueError:
        return command
    text = []
    for flag, value in zip(words, words[1:]):
        if flag in ("-m", "--message"):
            text.append(value)
        elif flag in ("-F", "--file"):
            path = Path(value.replace("/c/", "C:/", 1) if value.startswith("/c/") else value)
            try:
                text.append(path.read_text(encoding="utf-8"))
            except OSError:
                pass
    return "\n".join(text) or command


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    if not re.search(r"\bgit\b[^|;&]*\bcommit\b", command):
        return 0
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT,
                            capture_output=True, text=True).stdout.split()
    if "-a" in command.split() or "--all" in command:  # commit -a stages tracked changes
        staged += subprocess.run(["git", "diff", "--name-only"], cwd=ROOT,
                                 capture_output=True, text=True).stdout.split()
    ux = [f for f in staged if UX.match(f)]
    if not ux or any(f.startswith(MANUALS) for f in staged) or SKIP in message(command):
        return 0
    print("This commit changes what users see but not the user manuals:\n  "
          + "\n  ".join(ux[:12]) + ("\n  ..." if len(ux) > 12 else "")
          + "\n\nRefresh them (skill padelscore-manuals):\n"
          "  1. .venv/Scripts/python.exe -X utf8 scripts/make_manuals.py\n"
          "  2. update scripts/manual_texts.py if a screen, menu or process changed, and check\n"
          "     the screenshot cuts still frame the right part (look at the pages);\n"
          "  3. git add docs/manuales app/static/manuals, then commit again.\n"
          f"If no screen in the manuals is affected, put \"{SKIP}\" in the commit message.",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
