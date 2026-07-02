"""Config and secret field schema definitions.

This module defines the shape of config.nix and secrets.yaml — which fields
exist, their groups, validators, defaults, and lifecycle metadata.
"""

import os
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Optional

from envy.schemas.validators import is_email, is_url, non_empty
from envy.utils import DOTFILES_DIR, HOME_DIR


@dataclass
class FieldDef:
    group: str
    dest: str
    path: str
    yaml_path: str = ""
    prompt: str = ""
    default_fn: Callable[[], str] = field(default_factory=lambda: lambda: "")
    choices: list[str] = field(default_factory=list)
    condition: Optional[Callable[[dict], bool]] = None
    validators: list[Callable[[str], Optional[str]]] = field(default_factory=list)
    error_msg: str = ""
    ignore: bool = False
    required: bool = False


CONFIG_FIELDS = [
    FieldDef(group="BASE", dest="config", path="home.user", prompt="System username",
             default_fn=lambda: os.getenv("USER", "chi"), validators=[non_empty], required=True),
    FieldDef(group="BASE", dest="config", path="home.dir", prompt="Home directory",
             default_fn=lambda: str(HOME_DIR), validators=[non_empty], required=True),
    FieldDef(group="GIT", dest="config", path="git.name", prompt="Git user name",
             default_fn=lambda: os.getenv("USER", "chi"), validators=[non_empty], required=True),
    FieldDef(group="GIT", dest="config", path="git.email", prompt="Git user email",
             default_fn=lambda: f"{os.getenv('USER','chi')}@{subprocess.getoutput('hostname -f')}",
             validators=[is_email], required=True),
    FieldDef(group="PROXY", dest="config", path="proxy.status", prompt="Proxy status",
             default_fn=lambda: "none", choices=["none", "manual", "keep"], required=True),
    FieldDef(group="PROXY", dest="config", path="proxy.tun", prompt="Proxy TUN status",
             default_fn=lambda: "true", choices=["true", "false"],
             condition=lambda v: v.get("proxy.status") != "none"),
    FieldDef(group="ENV", dest="config", path="dotfiles.path", prompt="Dotfiles local path",
             default_fn=lambda: str(DOTFILES_DIR), ignore=True, required=True),
    FieldDef(group="VSCODE", dest="config", path="vscode.mode", prompt="VS Code config mode",
             default_fn=lambda: "remote", choices=["remote", "local"], required=True),
    FieldDef(group="LLM", dest="config", path="llm.steps.url", prompt="StepFun API base URL",
             default_fn=lambda: os.getenv("STEPFUN_BASE_URL", ""),
             validators=[non_empty, is_url], required=True),
    FieldDef(group="LLM", dest="config", path="llm.steps.model", prompt="StepFun default model",
             default_fn=lambda: "step-3.7-flash", validators=[non_empty], required=True),
    FieldDef(group="LLM", dest="config", path="llm.deepseek.url", prompt="DeepSeek API base URL",
             default_fn=lambda: "https://api.deepseek.com/v1", validators=[non_empty, is_url], required=True),
    FieldDef(group="LLM", dest="config", path="llm.deepseek.model", prompt="DeepSeek default model",
             default_fn=lambda: "deepseek-v4-pro", validators=[non_empty], required=True),
]

SECRET_FIELDS = [
    FieldDef(group="SECRET", dest="secret", yaml_path="home/passwd", path="home_passwd",
             prompt="System password", default_fn=lambda: os.getenv("USER", ""),
             validators=[non_empty], required=True),
    FieldDef(group="SECRET", dest="secret", yaml_path="proxy/url", path="proxy_url",
             prompt="Proxy URL", default_fn=lambda: "",
             condition=lambda v: v.get("proxy.status") != "none", validators=[is_url]),
    FieldDef(group="SECRET", dest="secret", yaml_path="llm/steps/apikey", path="llm_steps_apikey",
             prompt="StepFun API Key",
             default_fn=lambda: os.getenv("STEPFUN_API_KEY", os.getenv("API_KEY", "")),
             validators=[non_empty], required=True),
    FieldDef(group="SECRET", dest="secret", yaml_path="llm/deepseek/apikey", path="llm_deepseek_apikey",
             prompt="DeepSeek API Key", default_fn=lambda: ""),
]

ALL_FIELDS = CONFIG_FIELDS + SECRET_FIELDS

OBSOLETE_CONFIG_KEYS = ["llm.dashscope.url", "llm.dashscope.model"]
OBSOLETE_SECRET_PATHS = ["llm/dashscope/apikey"]
