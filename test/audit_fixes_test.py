import json

from flask import Flask, session

empires_server = __import__('empires-server')
import battle_engine
import game_settings
import mod_engine
import quest_engine
import save_engine

app = Flask(__name__)
app.secret_key = 'test'


def test_create_backup_is_bounded():
    with app.test_request_context():
        session['user_object'] = {"userInfo": {"player": {"level": 1}}}
        for i in range(save_engine.MAX_BACKUPS + 10):
            session['user_object']["userInfo"]["player"]["level"] = i
            save_engine.create_backup("backup " + str(i))

        depth = 0
        backup = session
        while "backup" in backup:
            backup = backup["backup"]
            depth += 1
        assert depth == save_engine.MAX_BACKUPS
        assert session["backup"]["message"] == "backup " + str(save_engine.MAX_BACKUPS + 9)
        # the snapshot is a copy, later changes don't leak into it
        session['user_object']["userInfo"]["player"]["level"] = 1000
        assert session["backup"]['user_object']["userInfo"]["player"]["level"] == save_engine.MAX_BACKUPS + 9


def test_next_campaign_with_battle_tuple():
    with app.test_request_context():
        session.sid = "0"
        session['user_object'] = {"userInfo": {"world": {"campaign": {"active": {}, "mastery": {}}}}}
        session["fleets"] = {}
        session["battle"] = ([100], [100], [], None)  # battle as created in the same request
        battle_engine.next_campaign_response({"map": "C000", "index": -1})
        assert session["battle"][:3] == ([100], [100], [])
        assert session["battle"][3].map_name == "C000"


def test_adjacent_factor_large_fleet():
    assert battle_engine.get_adjacent_factor(2, 3, 6) == 4
    assert battle_engine.get_adjacent_factor(0, 3, 6) == 0
    assert battle_engine.get_adjacent_factor(0, 1, 2) == 4


def test_lookup_indexes_keep_semantics():
    assert game_settings.lookup_item_by_code("U01")["-code"] == "U01"
    assert game_settings.lookup_item_by_name(game_settings.lookup_item_by_code("U01")["-name"])["-code"] == "U01"
    for code in ["DOES_NOT_EXIST", "QM01"]:  # unknown and duplicate codes still raise
        try:
            game_settings.lookup_item_by_code(code)
            assert False, code
        except ValueError:
            pass
    assert quest_engine.lookup_quest("Q0516")["_name"] == "Q0516"
    assert quest_engine.lookup_quest("DOES_NOT_EXIST") is None


def test_mod_json_patch(tmp_path):
    patch = tmp_path / "x.json.jsonpatch"
    patch.write_text(json.dumps([{"op": "replace", "path": "/a", "value": 3}]))
    assert json.loads(mod_engine.apply_mod(lambda: b'{"a": 1, "b": 2}', str(patch), patch.name)()) == {"a": 3, "b": 2}


def test_mod_xml_diff_returns_bytes(tmp_path):
    diff = tmp_path / "x.xml.xmldiff"
    diff.write_text('[update-attribute, /root/item[1], value, "2"]')
    result = mod_engine.apply_mod(lambda: b'<root><item value="1"/></root>', str(diff), diff.name)()
    assert isinstance(result, bytes)
    assert b'value="2"' in result


def test_mod_lookup(monkeypatch):
    monkeypatch.setattr(mod_engine, "mod", {"assets/29oct2012/gameSettings.xml": lambda: b"modded"})
    assert mod_engine.load("./assets/29oct2012/gameSettings.xml") == b"modded"
    assert mod_engine.load("./assets/29oct2012/en_US.xml") is None


def test_purchase_energy_refill_costs_cash():
    with app.test_request_context():
        session['user_object'] = {"userInfo": {"player": {"energy": 10, "energyMax": 25, "cash": 100}}}
        empires_server.purchase_energy_refill_response({})
        player = session['user_object']["userInfo"]["player"]
        assert player["energy"] == 25
        assert player["cash"] == 85


def test_unknown_service_gets_dummy_response():
    assert "UserService.useItem" in empires_server.SERVICE_HANDLERS
    assert "ClansService.buyCrest" not in empires_server.SERVICE_HANDLERS
