from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

@dataclass
class CommandTemplate:
    name: str
    description: str
    body: str
    scope: str  # "global" | "project"
    path: str


def sanitize_name(stem: str) -> str:
    s = stem.lower()
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    return s


def _load_dir(directory: Path, scope: str) -> List[CommandTemplate]:
    if not directory.exists() or not directory.is_dir():
        return []
    templates = []
    try:
        for p in directory.glob("*.md"):
            if p.is_file():
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                
                name = sanitize_name(p.stem)
                if not name:
                    continue
                
                lines = content.splitlines()
                first_idx = -1
                for i, line in enumerate(lines):
                    if line.strip():
                        first_idx = i
                        break
                
                if first_idx == -1:
                    description = ""
                    body = ""
                else:
                    first_line = lines[first_idx].strip()
                    m = re.match(r"^(?:#\s*)*description:\s*(.*)$", first_line, re.IGNORECASE)
                    if m:
                        description = m.group(1).strip()
                        if (description.startswith('"') and description.endswith('"')) or (description.startswith("'") and description.endswith("'")):
                            description = description[1:-1].strip()
                        body_lines = lines[first_idx + 1:]
                        body = "\n".join(body_lines).strip()
                    else:
                        description = first_line[:80].strip()
                        body = content.strip()
                
                templates.append(CommandTemplate(
                    name=name,
                    description=description,
                    body=body,
                    scope=scope,
                    path=str(p.absolute())
                ))
    except Exception:
        pass
    return templates


class CommandStore:
    def __init__(self, global_dir: Optional[str] = None):
        if global_dir:
            self.global_dir = Path(global_dir)
        else:
            self.global_dir = Path(os.path.expanduser("~/.pmharness/commands"))
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        try:
            created = False
            if not self.global_dir.exists():
                self.global_dir.mkdir(parents=True, exist_ok=True)
                created = True
            
            if created or len(list(self.global_dir.glob("*.md"))) == 0:
                example_file = self.global_dir / "example.md"
                if not example_file.exists():
                    example_file.write_text(
                        "description: Example custom command\n"
                        "Summarize the following and list 3 next steps:\n\n"
                        "$ARGUMENTS",
                        encoding="utf-8"
                    )
        except Exception:
            pass

    def list(self, repo: Optional[str] = None) -> List[CommandTemplate]:
        global_templates = _load_dir(self.global_dir, "global")
        project_templates = []
        if repo:
            project_dir = Path(repo) / ".pmharness" / "commands"
            project_templates = _load_dir(project_dir, "project")
        
        merged = {}
        for t in global_templates:
            merged[t.name] = t
        for t in project_templates:
            merged[t.name] = t
            
        return sorted(merged.values(), key=lambda x: x.name)

    def get(self, name: str, repo: Optional[str] = None) -> Optional[CommandTemplate]:
        sanitized = sanitize_name(name)
        for t in self.list(repo=repo):
            if t.name == sanitized:
                return t
        return None

    def render(self, name: str, args: str, repo: Optional[str] = None) -> Optional[str]:
        cmd = self.get(name, repo=repo)
        if not cmd:
            return None
        
        body = cmd.body
        has_arguments_token = "$ARGUMENTS" in body
        has_positional_token = bool(re.search(r"\$\d+", body))
        
        rendered = body.replace("$ARGUMENTS", args)
        words = args.split()
        
        def replace_pos(match: re.Match) -> str:
            num = int(match.group(1))
            idx = num - 1
            if 0 <= idx < len(words):
                return words[idx]
            return ""
            
        rendered = re.sub(r"\$(\d+)", replace_pos, rendered)
        
        if not has_arguments_token and not has_positional_token and args.strip():
            rendered = rendered + "\n\n" + args
            
        return rendered
