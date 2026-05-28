import json
from mtgcli.config import SEED_DATA_DIR


def load_theme_profiles() -> dict:
    path = SEED_DATA_DIR / "theme_profiles.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_theme_profile(theme: str) -> dict | None:
    profiles = load_theme_profiles()
    return profiles.get(theme)


def get_theme_packages(theme: str) -> dict:
    profile = get_theme_profile(theme)
    if not profile:
        return {}
    return profile.get("packages", {})


def get_package_definition(theme: str, package: str) -> dict | None:
    packages = get_theme_packages(theme)
    return packages.get(package)


def list_themes() -> list[str]:
    return list(load_theme_profiles().keys())


def list_packages(theme: str) -> list[str]:
    return list(get_theme_packages(theme).keys())
