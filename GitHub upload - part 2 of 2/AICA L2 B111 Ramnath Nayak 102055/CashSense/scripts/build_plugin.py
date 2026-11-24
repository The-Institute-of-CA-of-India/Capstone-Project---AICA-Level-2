"""Copy the agent skills (single source: cashsense/skills) into the Claude plugin, and print install steps."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC, DST = ROOT / "skills", ROOT / "plugin" / "cashsense" / "skills"


def build() -> list[str]:
    if DST.exists():
        shutil.rmtree(DST)
    names = []
    for skill in sorted(p for p in SRC.iterdir() if (p / "SKILL.md").exists()):
        shutil.copytree(skill, DST / skill.name)
        names.append(skill.name)
    return names


if __name__ == "__main__":
    names = build()
    print(f"Copied {len(names)} skills into the plugin: {', '.join(names)}")
    print("Install in Claude Code:  /plugin marketplace add", (ROOT / "plugin").as_posix())
    print("                         /plugin install cashsense@cashsense-local")
    print("Set CASHSENSE_HOME to the cashsense folder so the MCP server can read the API key from .env.")
