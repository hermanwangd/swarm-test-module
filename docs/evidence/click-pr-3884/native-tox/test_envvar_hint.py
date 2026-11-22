import click
from click.testing import CliRunner


def test_invalid_value_lists_individual_envvars():
    option = click.Option(["--units"], type=int, envvar=["WEATHER_UNITS", "UNITS"], show_envvar=True)
    command = click.Command("cli", params=[option])
    result = CliRunner().invoke(command, ["--units", "wrong"])
    assert result.exit_code == 2
    assert "Invalid value for '--units' (env var: 'WEATHER_UNITS', 'UNITS')" in result.output


def test_invalid_value_omits_empty_envvar_hint():
    for envvar in (None, "", []):
        option = click.Option(["--units"], type=int, envvar=envvar, show_envvar=True)
        result = CliRunner().invoke(click.Command("cli", params=[option]), ["--units", "wrong"])
        assert result.exit_code == 2
        assert "Invalid value for '--units': 'wrong' is not a valid integer." in result.output
