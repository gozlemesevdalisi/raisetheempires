"""Lists the strings of a package that still need a translation, as "key = English" lines.

Strings that will be filled in automatically (same English text already translated, item sentence names, placeholder
only strings) are skipped.

Usage: python tools/turkce/dump.py Package [start] [count]
"""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import SOURCE, TOKEN, load_translations, same_markup, strip_article  # noqa: E402


def main():
    package_name = sys.argv[1]
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 9
    translations, _ = load_translations()
    root = ET.parse(SOURCE).getroot()
    english_by_key = {(p.attrib["name"], s.attrib["key"]): s[0].text or "" for p in root for s in p}
    translated_english = {english_by_key.get((p, k)) for p, entries in translations.items() for k, t in entries.items()
                          if "#" not in k and same_markup(english_by_key.get((p, k), ""), t)}
    entries = translations.get(package_name, {})
    [package] = [p for p in root if p.attrib["name"] == package_name]

    pending = []
    seen = set()
    for string in package:
        key = string.attrib["key"]
        english = string[0].text or ""
        if key in entries or english in translated_english or english in seen:
            continue
        if not english.strip() or not TOKEN.sub("", english).strip(" ,.:!?-"):
            continue
        if key.endswith("_sentenceName"):
            menu_english = english_by_key.get((package_name, key[:-len("_sentenceName")] + "_menuName"))
            if menu_english is not None and strip_article(english) == strip_article(menu_english):
                continue
        seen.add(english)
        pending.append((key, english))

    print(f"# {package_name}: {len(pending)} pending", file=sys.stderr)
    for key, english in pending[start:start + count]:
        print(key + " = " + english.replace("\n", "\\n"))


if __name__ == "__main__":
    main()
