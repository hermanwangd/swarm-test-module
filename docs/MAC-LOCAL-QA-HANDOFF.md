# Mac 本機 Codex 交接：正式 ENGCIM QA Agent 的 Local Test

請接手並執行這次任務。使用者已授權在本機透過正式 ENGCIM 入口提交一個公開 PR 做 Local Test。範圍到本地雙 runner 的逐案報告為止。你擔任派工、環境準備、監看與證據查核；測試設計、DSL 和產品測試執行由正式 Agent 工作流完成。若已有同一筆交辦，先核對並接續，避免重複派工。

## 已知狀態

Linux 工作區的 Codex 曾為 Click #3884、#3902 及 Commons CLI #450 設計或執行案例。本 repo 留有那些實驗的報告。它們可說明模組能力，不能作為這次 Mac 正式 Agent 的執行紀錄。交接時尚無此次驗收的 mission ID 或 agent run ID。歷史 Mac daemon 名稱為 Herman-MBP2023deMacBook-Pro.local；請以當前 daemon 和 workspace 讀回值為準。

| 來源 | 交接時的版本與用途 |
|---|---|
| hermanwangd/swarm-test-module PR #1 | 功能基準 ade7c8b3da9562f43ebf37b0263f0a8a5231df01；skills/project-test/SKILL.md 定義雙 runner 比對。Maven 模組版本 1.0.0。 |
| hermanwangd/Auto_Regression_Test_Framework | plug-in-module 分支上的 597064a9c75c6323a164a06d050110e16d165aca；Framework 0.3.2。預期在相鄰 checkout。 |
| hermanwangd/engcim-swarm PR #31 | 17770fb3e345a3367e525eef31339ee81b361f68 已匯入上述 skill。Supervisor 入口和派工規則在 supervisor/bootstrap/overlays/claude/engcim/supervisor.md。 |

## 在 Mac 執行

1. 用 uname、hostname 確認本機；用實際安裝的 multica CLI help 核對命令，再讀取登入身分、ENGCIM workspace、daemon status、QA Agent 與其 runtime ID。比對 Mac 裝置與 runtime。目前的 QA provider 與 daemon 身分能否使用 Kimi 都需要現場確認。若綁定不同，記錄實際值；變更正式綁定前先取得授權。
2. 確認 daemon 工作目錄能讀取專案 checkout、QA skill、原生 runner、Java 17、模組及 Framework JAR。依 [模組設定](../README.md) 核對本機實際路徑與 SHA-256。在本機安全配置處理授權。Linux 的絕對路徑及舊 handoff 不可直接套用。比對實際載入的 skill 與 repo 版本；磁碟上 clone 完成只證明原始碼存在。
3. 走 ENGCIM Supervisor 既有入口提交。**交給正式 Agent 的使用者訊息只有以下一行**；交接文件供本機 Codex 使用，勿附上案例、計畫、DSL 或預期答案。

   https://github.com/pallets/click/pull/3896

4. 記錄 mission／issue、QA Agent、runtime 及相關 run ID。追蹤到終態，保留獨立 Reviewer 和 Verifier 的身分及交接證據。由 Agent 找需求、核對既有斷言、補缺口。對每個範圍內的既有案例判斷可移植性；新增案例應提供 Framework DSL 及產品原生對應案例。對可比案例使用相同產品 SHA、輸入與預期行為，在該本地工作流中執行雙 runner。
5. 交回逐案表：AC 與來源、重用或新增、原生案例／結果、Framework 案例／結果、差異或無法移植的原因、兩邊 log 或 receipt。附實際受測 SHA、執行者及 run ID。阻塞時回報停在哪個角色或命令、原始錯誤及已嘗試的修復。缺一次執行、環境不同或兩邊同時 FAIL，都不能判為雙 runner 通過。

完成依據是可追溯到這次正式任務的本地執行證據。新 Codex 自己跑樣本、既有報告、單邊綠燈、CI 或 SIT 結果均不能替代。
