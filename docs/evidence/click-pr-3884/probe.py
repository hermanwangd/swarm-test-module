"""Print the observed public Click behavior from the specified source archive."""
import sys
sys.path.insert(0, sys.argv[1])
import click
from click.testing import CliRunner
assert click.__file__.startswith(sys.argv[1] + "/")
def observe(env, args):
    option = click.Option(["--region"], required=True, envvar=env, show_envvar=True)
    result = CliRunner().invoke(click.Command("weather", params=[option]), args)
    return result.exit_code, result.output
if sys.argv[2] == "sequence":
    code, output = observe(("PRIMARY REGION", "FALLBACK"), [])
    print(code, output.splitlines()[-1])
else:
    for env in ["", []]:
        for args in [[], ["--help"]]:
            ref = observe(None, args)
            actual = observe(env, args)
            print(actual[0], actual == ref)
