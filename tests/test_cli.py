from azure_cost_exporter import cli


def test_get_args():
    params = cli.get_args(["-l", "info", "-c", "config-test.yaml"])
    assert params.loglevel == "INFO"
    assert params.config == "config-test.yaml"
