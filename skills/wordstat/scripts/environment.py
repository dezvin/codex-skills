"""Load named Windows user settings without printing or persisting credentials."""

import os


SETTING_NAMES = (
    "WORDSTAT_API_KEY", "WORDSTAT_IAM_TOKEN", "WORDSTAT_FOLDER_ID",
    "WORDSTAT_CAPACITY_BUCKET", "WORDSTAT_CAPACITY_RPS", "WORDSTAT_CAPACITY_HOURLY",
    "WORDSTAT_SUGGEST_LOCAL_RPS", "WORDSTAT_SUGGEST_LOCAL_PER_MINUTE",
    "WORDSTAT_TARIFF_RUB_PER_1000", "WORDSTAT_TARIFF_CHECKED_ON",
    "TOPVISOR_USER_ID", "TOPVISOR_API_KEY", "TOPVISOR_PROXY_MODE",
)


def load_windows_user_environment() -> None:
    """Fill missing process values; explicit process overrides remain authoritative."""
    if os.name != "nt":
        return
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            for name in SETTING_NAMES:
                if name in os.environ:
                    continue
                # A process-supplied auth type must not acquire the other type.
                if ((name == "WORDSTAT_API_KEY" and os.environ.get("WORDSTAT_IAM_TOKEN"))
                        or (name == "WORDSTAT_IAM_TOKEN" and os.environ.get("WORDSTAT_API_KEY"))):
                    continue
                try:
                    value, kind = winreg.QueryValueEx(key, name)
                except FileNotFoundError:
                    continue
                if kind in {winreg.REG_SZ, winreg.REG_EXPAND_SZ} and isinstance(value, str):
                    os.environ[name] = value
    except OSError:
        return
