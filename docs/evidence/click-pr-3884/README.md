# External project acceptance run

Upstream [pallets/click PR 3884](https://github.com/pallets/click/pull/3884)
specifies how environment variable names appear in option help and errors.
The PR table, CHANGES.md and upstream behavior tests supply the expected
behavior. Click expresses these scenarios in pytest. The probe uses the
public Click API with a different option name and input values.

The sequence case observes the exact missing-option message, including quoting
a name containing a space. The empty case compares complete help and error
output against the same command with no environment variable, for both an empty
string and an empty list. The leading numbers in the observations are Click's
exit codes. The probe exits normally so the Framework can judge its output.

baseline.json records observations from the probe invoked directly against the
base source archive. report.json records execution against the PR head through
the published Test Module and its Framework. The same probe and expected values
were used for both versions. Each archive was created with git archive from
the exact revision's src tree, containing only click/. The probe imports from
that archive under isolated Python and checks the actual module location.
Coverage is local to the two selected behaviors. Automatic environment prefixes
and the complete upstream regression suite are outside this run.
