import click
from click.testing import CliRunner


def test_custom_metavar_survives_narrow_help():
    metavar = "SOURCE-ARCHIVE-LOCATION"

    @click.command()
    @click.argument("source", metavar=metavar)
    def extract(source):
        pass

    result = CliRunner().invoke(extract, ["--help"], terminal_width=22)
    assert result.exit_code == 0
    assert metavar in result.output.split()
