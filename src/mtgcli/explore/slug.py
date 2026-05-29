import re


def commander_to_slug(name: str) -> str:
    """Converts a commander name to a URL slug.

    Examples:
        Omnath, Locus of Rage -> omnath-locus-of-rage
        Chishiro, the Shattered Blade -> chishiro-the-shattered-blade
    """
    name = name.lower()
    name = re.sub(r"[''`']", "", name)
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"\s+", "-", name.strip())
    name = re.sub(r"-+", "-", name)
    return name.strip("-")
