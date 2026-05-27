from mtgcli.export.moxfield import export_moxfield_line

def test_export_moxfield_line_full_info():
    card = {
        "name": "Sol Ring",
        "set_code": "lcc",
        "collector_number": "299"
    }
    expected = "1 Sol Ring (LCC) 299"
    assert export_moxfield_line(card) == expected

def test_export_moxfield_line_missing_info():
    card = {
        "name": "Sol Ring"
    }
    expected = "1 Sol Ring"
    assert export_moxfield_line(card) == expected
