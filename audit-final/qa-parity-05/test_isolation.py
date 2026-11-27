"""Isolated TestClient only: no listening server, container or target requests."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
import socket
from fastapi.testclient import TestClient
import pytest

spec=importlib.util.spec_from_file_location('qa_app',Path(__file__).with_name('qa_app.py'))
qa=importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


def test_parity_fixture_and_isolation(tmp_path):
    with patch('backend.app.main.worker_loop', side_effect=AssertionError('worker started')), patch('backend.app.main.external_lab_dispatcher_loop', side_effect=AssertionError('dispatcher started')), patch('socket.socket.connect', qa.deny_connect), patch('socket.socket.connect_ex', qa.deny_connect), patch('socket.getaddrinfo', qa.deny_connect):
        app=qa.build_app(tmp_path/'synthetic.sqlite3','synthetic-test-only')
        with TestClient(app) as client:
            assert client.get('/api/projects').status_code==401
            response=client.post('/api/auth/login',json={'password':'synthetic-test-only'})
            assert response.status_code==200, response.text
            identities=client.get('/api/projects/1/identities').json()
            assert {i['role'] for i in identities}=={'admin','userA','userB'}
            for resource in (1,2):
                rows=client.get(f'/api/projects/1/matrix?operation_id=1&resource_id={resource}').json()
                assert len(rows)==3
                assert {r['resolved_decision'] for r in rows}=={'ALLOW','DENY'}
            results=client.get('/api/runs/1/results').json()
            assert len(results)==6
            assert all(r['response_metadata']['evidence'] is not None for r in results)
            comparison=client.get('/api/projects/1/runs/1/comparison').json()
            assert len(comparison['cases'])==6
            for case in comparison['cases']:
                manual,t18,zap=case['methods']
                assert manual['execution_status']==zap['execution_status']=='NOT_RUN'
                assert t18['provenance'].startswith('run:1:result:')
                assert t18['observation']['response_metadata']['evidence'] is not None
            assert client.post('/api/projects/1/runs',json={}).status_code==403
            assert client.post('/api/projects/1/batch-runs',json={}).status_code==403
            with pytest.raises(PermissionError):
                socket.socket().connect(('127.0.0.1',8000))
            with pytest.raises(PermissionError):
                socket.getaddrinfo('example.org',443)
        with app.state.session_factory() as session:
            run=session.get(qa.Run,1)
            assert 'synthetic' in run.snapshot['provenance']
            assert run.status=='COMPLETED'
