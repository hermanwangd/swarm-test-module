# TAA／gTAA 對齊說明

## 範圍與結論

本文件描述 `swarm-product-test` standalone module 如何對應 ISTQB gTAA（Generic Test Automation Architecture）。結論是：**module boundary 大致遵循 gTAA 的分層與抽象原則，但本 repo 不是完整 TAS，不能單獨宣稱整體 gTAA compliant**。完整 TAS 仍包含外部 test framework JAR、reviewed suites、provider contracts、實際 SUT 與執行環境。

gTAA 是架構參考模型，不是要求每個產品都實作所有層級的認證清單。未使用自動化 test generation 時，該層可以缺席；但已存在的 execution、logging、reporting 與 harness 驗證必須 fail closed。

## 分層對照

| gTAA 面向 | 本模組實作 | 判定 |
| --- | --- | --- |
| Test Generation | `preparation/PreparationService` 只產生 `PREPARED_NOT_APPROVED` proposal；固定 candidates、獨立 oracle review、追溯與範圍檢查都在 execution 前完成 | 符合其宣告範圍；不宣稱 model-based generation |
| Test Definition | reviewed suite、manifest、profile、fixtures、oracles 與 `public-projects/sqlite/cases.json` 將測試資料、程序及 oracle 與 SUT 實作分離 | 對齊 |
| Test Execution | `DefaultProductTestingModule` 做請求驗證；`FrameworkCliTransport` 依序執行 `run`、`validate-evidence`、`report`，並由外部 framework 產生 canonical verdict | 對齊 |
| Logging／Reporting | `CanonicalEvidence`、`CoverageArtifacts` 與 `ProductTestReceipt` 保留 typed outcome、framework verdict、run identity、artifact path 與 SHA-256 | 對齊；Python harness 必須以非 `assert` 檢查保護最終 evidence |
| Test Adaptation | 實際 REST／CLI／NATS／gRPC／JDBC provider adaptation 屬於外部 framework；本模組透過 `FrameworkExecutionPort` 只保留窄執行邊界 | 部分對齊；A01 與 JDBC 特例目前是有邊界的 adapter extensions |
| Configuration Management | request pins 綁定 repository revisions、suite、profile、requirement mapping、reviewed handoff；framework JAR 與輸出根目錄由獨立部署設定提供 | 對齊 |
| Test Management | requirement-to-test mapping、reviewed handoff、receipt 與 evidence tree 提供追溯；外部 test-management 系統不在本 repo | 部分對齊；完整流程需外部證據 |
| Project Management | Maven build、Git history、GitHub Actions 與 release 流程支援 TAS 演進 | 部分對齊；CI 應持續執行 Python harness 測試 |

## 已知的 adapter 特例

`FrameworkCliTransport` 目前直接包含兩類特例：

- A01 reviewed launch／fixture lease pin。
- JDBC protected child observation 與 driver recheck。

這是刻意的最小實作，不應擴大成通用 provider 平台。若加入第三類特例，應先抽出窄 adapter extension interface；在此之前，不值得為形式上的分層增加複雜度。

## 驗證規則

- 執行 evidence 的 Python harness 不使用可被 `python -O` 或 `PYTHONOPTIMIZE=1` 移除的 `assert` 作為輸入、pin、exit-code、verdict 或 artifact 驗證。
- 任一檢查失敗必須以非零 exit 結束，且不得產生 `"status": "passed"` evidence。
- CI 應執行 Java suite、consumer import smoke、packaging checks，以及 `python3 -B -m unittest discover -s scripts/tests -v`。
- 本模組產生的 evidence 仍是 `framework_verification_only`，`release_evidence_eligible` 恆為 false；它不是 SIT／release acceptance。

## 不屬於本文件的結論

本文件不證明外部 framework、實際 SUT、Cognee、Swarm host、SIT 環境或發佈流程本身合規。這些需要以對應 repo、reviewed suites、部署設定與執行 evidence 另行評估。
