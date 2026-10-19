def test_manifest(cliente):
    r = cliente.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json")
    m = r.json()
    assert m["display"] == "standalone"
    assert m["start_url"] == "/"
    assert m["lang"] == "pt-BR"
    tamanhos = {i["sizes"] for i in m["icons"]}
    assert {"192x192", "512x512"} <= tamanhos
    assert any(i.get("purpose") == "maskable" for i in m["icons"])


def test_icones_existem(cliente):
    for icone in cliente.get("/manifest.webmanifest").json()["icons"]:
        r = cliente.get(icone["src"])
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"


def test_sw_servido_na_raiz(cliente):
    r = cliente.get("/sw.js")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    assert r.headers["Service-Worker-Allowed"] == "/"
    assert r.headers["Cache-Control"] == "no-cache"


def test_offline_publico(cliente):
    r = cliente.get("/offline")
    assert r.status_code == 200
    assert "Sem conexão" in r.text


def test_paginas_apontam_para_o_manifest(cliente):
    assert '<link rel="manifest" href="/manifest.webmanifest">' in cliente.get("/login").text


def test_favicon(cliente):
    r = cliente.get("/favicon.ico")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
