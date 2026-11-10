"""Fresh-host and profile boundaries for the plugin's own HTTP API."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_api():
    name = 'hc_portability_api_under_test'
    spec = importlib.util.spec_from_file_location(name, ROOT / 'dashboard' / 'plugin_api.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_router_mounts_without_optional_multipart(monkeypatch):
    # JSON/base64 uploads do not require the optional multipart parser. Blocking
    # both import spellings reproduces a clean host, even in a populated dev venv.
    monkeypatch.setitem(sys.modules, 'python_multipart', None)
    monkeypatch.setitem(sys.modules, 'multipart', None)
    mod = load_api()
    paths = {route.path for route in mod.router.routes}
    assert {'/today', '/family', '/intake64'} <= paths


def make_client(monkeypatch, tmp_path, family_file):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    mod = load_api()
    tools = mod._modules()[1]
    store = tools.Store(root=tmp_path / 'profile-data', output_dir=tmp_path / 'volume' / 'packets')
    rt = tools.Runtime(lambda k, d=None: str(family_file) if k == 'family_config' else d, store=store)
    monkeypatch.setattr(mod, '_runtime', lambda: rt)
    app = FastAPI()
    app.include_router(mod.router)
    return mod, rt, TestClient(app)


def test_plugin_download_works_outside_the_general_workspace(monkeypatch, tmp_path, family_file):
    import base64
    import json
    _, rt, client = make_client(monkeypatch, tmp_path, family_file)
    folder = rt.store.packet_dir('2026-11-02')
    pdf = folder / 'nova_practice.pdf'
    pdf.write_bytes(b'%PDF-1.4\nportable fixture\n')
    (folder / 'packet.json').write_text(json.dumps({
        'children': {'nova': {}}, 'files': {'nova': pdf.name},
    }), encoding='utf-8')
    response = client.post('/download', json={'path': str(pdf.resolve())})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['name'] == pdf.name and result['content_type'] == 'application/pdf'
    assert result['size'] == len(pdf.read_bytes())
    assert base64.b64decode(result['data_b64'], validate=True) == pdf.read_bytes()
    assert response.headers['cache-control'] == 'no-store'


def test_download_denies_unregistered_and_other_profile_files(monkeypatch, tmp_path, family_file):
    import json
    _, rt, client = make_client(monkeypatch, tmp_path, family_file)
    folder = rt.store.packet_dir('2026-11-02')
    (folder / 'packet.json').write_text(json.dumps({'children': {'nova': {}}, 'files': {}}), encoding='utf-8')
    stray = folder / 'not-a-packet.pdf'
    stray.write_bytes(b'%PDF-1.4\nunregistered')
    outside = tmp_path / 'other-profile' / 'private.pdf'
    outside.parent.mkdir()
    outside.write_bytes(b'%PDF-1.4\nprivate')
    for path in (str(stray), str(outside), str(family_file), '../private.pdf', str(folder / 'packet.json')):
        response = client.post('/download', json={'path': path})
        assert response.status_code == 400, (path, response.text)
        assert 'data_b64' not in response.json()


def test_download_recorded_teacher_original(monkeypatch, tmp_path, family_file):
    import base64
    import json
    _, rt, client = make_client(monkeypatch, tmp_path, family_file)
    folder = rt.store.child_dir('nova')
    original = folder / 'teacher.txt'
    original.write_bytes(b'Class topic: arrays')
    (folder / 'materials.jsonl').write_text(json.dumps({'file': str(original), 'date': '2026-11-02'}) + '\n', encoding='utf-8')
    response = client.post('/download', json={'path': str(original)})
    assert response.status_code == 200, response.text
    assert base64.b64decode(response.json()['data_b64']) == original.read_bytes()


def test_jobs_do_not_cross_profile_data_roots(monkeypatch, tmp_path, family_file):
    mod, rt, client = make_client(monkeypatch, tmp_path, family_file)
    # Same API module may serve requests for several profile contexts.
    receipt = mod._start_job(lambda: {'private': 'original family'})
    assert client.get('/jobs/' + receipt['job']).status_code == 200
    tools = mod._modules()[1]
    other = tools.Runtime(lambda k, d=None: str(family_file) if k == 'family_config' else d,
                          store=tools.Store(root=tmp_path / 'other-profile'))
    monkeypatch.setattr(mod, '_runtime', lambda: other)
    response = client.get('/jobs/' + receipt['job'])
    assert response.status_code == 404
    assert 'original family' not in response.text
