# Pinned declarative inputs for standalone local tests

These two files are byte-for-byte copies from
`hermanwangd/Auto_Regression_Test_Framework` commit
`597064a9c75c6323a164a06d050110e16d165aca`:

| Local file | Original file | SHA-256 |
| --- | --- | --- |
| `cli_process_v0_3.yaml` | `docs/02-architecture/contracts/provider-contracts/cli_process_v0_3.yaml` | `5a8d8d9e211d741f23def255c8cf0699e9f4d3735d5f2d47ca1795d414c010be` |
| `review-input.json` | `samples/41-product-testing/reviewed_local/review-input.json` | `3fd8fc6adccd10d0b4a25a2e18d293ef2bbe58cf9fd8339ad6150b5ad9a56b6f` |

They are test-only declarative inputs, excluded from the runtime JAR. The public
SQLite harness no longer resolves files through an assumed `../..` framework
checkout. Oracle, contract and review-template bytes are unchanged; the local
policy updates only file locations and the relocated harness digest. Execution
still requires a separately pinned Framework JAR and the independent local
policy pin. No runner, DSL implementation or provider code is copied.
