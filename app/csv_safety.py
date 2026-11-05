import unicodedata


_FORMULA_PREFIXES = {"=", "+", "-", "@"}


def safe_csv_cell(value):
    if not isinstance(value, str):
        return value

    first_significant = next(
        (
            character
            for character in value
            if not character.isspace()
            and unicodedata.category(character) not in {"Cc", "Cf"}
        ),
        "",
    )
    if first_significant in _FORMULA_PREFIXES:
        return "'" + value
    return value
