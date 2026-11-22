# Existing CLI acceptance criteria

Scope: the standalone CLI entry of the published 1.0.0 artifact. These criteria
restate README's invocation/deployment contract and ProductTestCli's existing
diagnostics. They do not claim business coverage, native Swarm adoption or SIT.

- AC-CLI-1: Malformed invocation (including missing or excess arguments) exits 2,
  prints `product-test: usage: product-test run --request <request.json>` to stderr,
  and does not read the requested file or invoke the Framework.
- AC-CLI-2: A syntactically readable request cannot execute without deployment
  configuration. With no deployment environment, exit is 2 and stderr is
  `product-test: Missing deployment binding: SWARM_PRODUCT_TEST_FRAMEWORK_JAR`.

This is a focused project acceptance slice for PR #1's executable packaging and
source-to-case workflow. Functional suite execution, schema hardening and all
other README capabilities retain their separate test evidence and are outside
this two-AC inventory.
