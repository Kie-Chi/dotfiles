"""Linux-only application schemas used by ``envy doctor``."""

from envy.schemas.common.apps import AppSpec
from envy.utils import HOME_DIR


APP_SPECS: dict[str, AppSpec] = {
    "chrome": AppSpec(
        name="Google Chrome",
        packages=["google-chrome"],
        commands=["google-chrome-stable"],
        processes=["chrome", "google-chrome-stable"],
        state_paths=[HOME_DIR / ".config/google-chrome"],
        checkers=["chrome_account"],
    ),
    "feishu": AppSpec(
        name="Feishu",
        packages=["feishu"],
        commands=["bytedance-feishu"],
        processes=["bytedance-feishu", "Feishu"],
        state_paths=[HOME_DIR / ".config/bytedance-feishu"],
        login_hint="Open Feishu and confirm the account avatar/workspace is present.",
    ),
    "tencent-meeting": AppSpec(
        name="Tencent Meeting",
        packages=["wemeet"],
        commands=["wemeet"],
        processes=["wemeet"],
        state_paths=[HOME_DIR / ".config/wemeet"],
        login_hint="Open Tencent Meeting and confirm the account page is signed in.",
    ),
    "wps-office": AppSpec(
        name="WPS Office",
        packages=["wpsoffice-cn"],
        commands=["wps"],
        processes=["wps", "wpsoffice"],
        state_paths=[HOME_DIR / ".config/Kingsoft"],
        login_hint="Open WPS Office and sign in if you use WPS Cloud or account sync.",
    ),
    "okular": AppSpec(
        name="Okular",
        packages=["okular"],
        commands=["okular"],
        processes=["okular"],
    ),
    "sunshine": AppSpec(
        name="Sunshine",
        packages=["sunshine"],
        commands=["sunshine"],
        processes=["sunshine"],
        should_run=True,
        state_paths=[HOME_DIR / ".config/sunshine"],
    ),
}

APP_ALIASES: dict[str, str] = {
    "google-chrome": "chrome",
    "lark": "feishu",
    "meeting": "tencent-meeting",
    "tencentmeeting": "tencent-meeting",
    "wps": "wps-office",
    "wpsoffice": "wps-office",
    "wpsoffice-cn": "wps-office",
}


__all__ = ["APP_ALIASES", "APP_SPECS"]
