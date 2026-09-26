import xml.etree.ElementTree as ET
from save_engine import install_path
import mod_engine
import os


def language_strings():
    path = os.path.join(install_path(), "assets/29oct2012/en_US.xml")
    modded = mod_engine.load(path)  # e.g. a translation mod
    root = ET.fromstring(modded) if modded is not None else ET.parse(path).getroot()
    return {text.attrib["key"]: text[0].text for pkg in root for text in pkg}
