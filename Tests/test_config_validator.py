from pathlib import Path
import yaml


def test_example_config_has_required_sections():
    data=yaml.safe_load(Path('Config/config.example.yaml').read_text(encoding='utf-8'))
    assert data['system']['max_position_logics']==2
    for section in ('mt5','atas','ai','engine'):
        assert section in data
    assert isinstance(data['atas']['require_mbo'], bool)
