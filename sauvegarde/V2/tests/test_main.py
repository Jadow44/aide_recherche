import pytest
import pandas as pd
import os
from unittest.mock import patch, MagicMock
from main import update_proxies_if_needed, ensure_directory_exists, main

@pytest.fixture
def sample_proxies():
    return ['proxy1', 'proxy2', 'proxy3']

def test_update_proxies_if_needed():
    assert update_proxies_if_needed('non_existent_file') is True

    with patch('os.path.getmtime') as mock_getmtime:
        mock_getmtime.return_value = (datetime.now() - timedelta(hours=2)).timestamp()
        assert update_proxies_if_needed('existing_file') is True

    with patch('os.path.getmtime') as mock_getmtime:
        mock_getmtime.return_value = (datetime.now() - timedelta(minutes=30)).timestamp()
        assert update_proxies_if_needed('existing_file') is False

def test_ensure_directory_exists(tmp_path):
    test_dir = tmp_path / "test_dir"
    ensure_directory_exists(test_dir)
    assert test_dir.exists()

def test_main(mocker):
    mocker.patch('main.update_proxies_if_needed', return_value=False)
    mocker.patch('main.read_proxies_from_excel', return_value=sample_proxies())
    mocker.patch('main.select_proxy', return_value='proxy1')
    mocker.patch('main.google_scholar_search', return_value=[{'title': 'test', 'link': 'http://test.com', 'summary': 'summary'}])
    mocker.patch('main.semantic_scholar_search', return_value=[{'title': 'test', 'link': 'http://test.com', 'summary': 'summary'}])
    mocker.patch('main.clean_data', return_value=pd.DataFrame([{'title': 'test', 'summary': 'summary'}]))
    mocker.patch('main.preprocess_data', return_value=pd.DataFrame([{'title': 'test', 'processed_summary': 'summary'}]))
    mocker.patch('main.spacy.load', return_value=MagicMock())
    mocker.patch('main.ensure_directory_exists')
    mocker.patch('main.pd.DataFrame.to_excel')
    
    main()
    # Add assertions to check expected behaviors
