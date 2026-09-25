"""Builds the Turkish translation mod (mods/turkce) from the translation files in tools/turkce/ceviri.

Translation files are named after the package in en_US.xml (e.g. Main.tsv) and contain one line per string:

    key = Turkish text
    key#index = Turkish text for one variation (optional, variations are derived otherwise)

Lines starting with # are comments, a literal \\n is a line break. Untranslated strings stay English.

Variations (gender, singular/plural, articles) don't exist in Turkish, they are derived from the translated original by
swapping in the variation's own {tokens}. Item sentence names ("a Tank") are derived from the translated menu name.

Usage:
    python tools/turkce/build.py            build the mod
    python tools/turkce/build.py --ascii    build with s/g/I instead of ş/ğ/İ (for fonts without those letters)
    python tools/turkce/build.py --check    only validate and report coverage
"""
import argparse
import collections
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SOURCE = os.path.join(ROOT, "assets", "29oct2012", "en_US.xml")
TRANSLATIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ceviri")
TARGET = os.path.join(ROOT, "mods", "turkce", "assets", "29oct2012", "en_US.xml")

TOKEN = re.compile(r"\{[^{}]*\}")
TAG = re.compile(r"<[^<>]+>")
ASCII = str.maketrans("şŞğĞİ", "sSgGI")


def token_name(token):
    return re.split(r"[,\s}]", token[1:], 1)[0]


def load_translations():
    translations = {}
    problems = []
    for file_name in sorted(os.listdir(TRANSLATIONS)):
        if not file_name.endswith(".tsv"):
            continue
        package = file_name[:-4]
        entries = translations.setdefault(package, {})
        with open(os.path.join(TRANSLATIONS, file_name), encoding="utf-8") as f:
            for line_number, line in enumerate(f, 1):
                line = line.rstrip("\r\n")
                if not line.strip() or line.startswith("#"):
                    continue
                if " = " not in line:
                    problems.append(f"{file_name}:{line_number}: no ' = ' separator")
                    continue
                key, text = line.split(" = ", 1)
                if key in entries:
                    problems.append(f"{file_name}:{line_number}: duplicate key {key}")
                entries[key] = text.replace("\\n", "\n")
    return translations, problems


def same_markup(english, turkish):
    return (collections.Counter(TOKEN.findall(english)) == collections.Counter(TOKEN.findall(turkish)) and
            collections.Counter(TAG.findall(english)) == collections.Counter(TAG.findall(turkish)))


def derive_variation(turkish, english_original, english_variation):
    original_tokens = TOKEN.findall(english_original)
    variation_tokens = TOKEN.findall(english_variation)
    if not variation_tokens:
        return turkish
    by_name = {}
    for token in variation_tokens:
        by_name.setdefault(token_name(token), []).append(token)
    if collections.Counter(token_name(t) for t in original_tokens) != \
            collections.Counter(token_name(t) for t in variation_tokens):
        return None
    used = collections.Counter()

    def swap(match):
        name = token_name(match.group(0))
        candidates = by_name.get(name)
        if not candidates:
            return match.group(0)
        token = candidates[min(used[name], len(candidates) - 1)]
        used[name] += 1
        return token

    return TOKEN.sub(swap, turkish)


def build(ascii_only=False, check_only=False):
    translations, problems = load_translations()
    tree = ET.parse(SOURCE)
    root = tree.getroot()

    english_by_key = {}
    for package in root:
        for string in package:
            english_by_key[(package.attrib["name"], string.attrib["key"])] = string[0].text or ""

    known_keys = set(english_by_key)
    for package, entries in translations.items():
        for key in entries:
            if (package, key.split("#")[0]) not in known_keys:
                problems.append(f"{package}.tsv: unknown key {key}")

    # translation memory: identical English text gets the same translation everywhere
    memory = {}
    for package, entries in translations.items():
        for key, text in entries.items():
            english = english_by_key.get((package, key))
            if english is not None and "#" not in key and english not in memory and same_markup(english, text):
                memory[english] = text

    coverage = collections.Counter()
    totals = collections.Counter()
    words_done = collections.Counter()
    words_total = collections.Counter()
    underived = 0

    for package in root:
        package_name = package.attrib["name"]
        entries = translations.get(package_name, {})
        for string in package:
            key = string.attrib["key"]
            original = string[0]
            english = original.text or ""
            words = len(english.split())
            totals[package_name] += 1
            words_total[package_name] += words

            turkish = entries.get(key)
            if turkish is not None and not same_markup(english, turkish):
                problems.append(f"{package_name}.tsv: {key}: placeholders/tags differ\n    EN: {english}\n    TR: {turkish}")
                turkish = None
            if turkish is None and key.endswith("_sentenceName"):
                menu_key = key[:-len("_sentenceName")] + "_menuName"
                menu_english = english_by_key.get((package_name, menu_key))
                menu_turkish = entries.get(menu_key) or memory.get(menu_english)
                if menu_turkish and re.sub(r"^(a|an|some) ", "", english) == menu_english:
                    turkish = menu_turkish
            if turkish is None and english.strip() and not TOKEN.sub("", english).strip(" ,.:!?-"):
                turkish = english  # only placeholders, nothing to translate
            if turkish is None:
                turkish = memory.get(english)
            if turkish is None:
                continue

            coverage[package_name] += 1
            words_done[package_name] += words
            original.text = turkish.translate(ASCII) if ascii_only else turkish
            for variation in string[1:]:
                variation_english = variation.text or ""
                override = entries.get(f"{key}#{variation.attrib.get('index')}")
                if override is not None:
                    if not same_markup(variation_english, override):
                        problems.append(f"{package_name}.tsv: {key}#{variation.attrib.get('index')}: placeholders/tags differ")
                        continue
                    text = override
                elif not TOKEN.search(english) and not TOKEN.search(variation_english):
                    text = turkish  # noun forms (a/the/some/plural) are all the same in Turkish
                else:
                    text = derive_variation(turkish, english, variation_english)
                    if text is None:
                        underived += 1
                        continue
                variation.text = text.translate(ASCII) if ascii_only else text

    for problem in problems:
        print("PROBLEM:", problem)

    print(f"{'package':24}{'strings':>16}{'words':>18}")
    for package in root:
        name = package.attrib["name"]
        if coverage[name]:
            print(f"{name:24}{coverage[name]:>7}/{totals[name]:<8}{words_done[name]:>8}/{words_total[name]:<9}")
    done, total = sum(coverage.values()), sum(totals.values())
    print(f"{'TOTAL':24}{done:>7}/{total:<8}{sum(words_done.values()):>8}/{sum(words_total.values()):<9}"
          f" ({100 * sum(words_done.values()) / max(sum(words_total.values()), 1):.1f}% of words)")
    if underived:
        print("variations kept English (token mismatch):", underived)

    if not check_only:
        os.makedirs(os.path.dirname(TARGET), exist_ok=True)
        tree.write(TARGET, encoding="UTF-8", xml_declaration=True)
        print("written", os.path.relpath(TARGET, ROOT))
    return 1 if problems else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ascii", action="store_true", help="replace ş, ğ and İ with s, g and I")
    parser.add_argument("--check", action="store_true", help="validate and report without writing the mod")
    arguments = parser.parse_args()
    sys.exit(build(arguments.ascii, arguments.check))
