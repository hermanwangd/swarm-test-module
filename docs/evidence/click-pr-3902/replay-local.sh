#!/bin/sh
# Replay the checked-in local acceptance case from a QA Module checkout.
set -eu
case_dir=$(CDPATH= cd "$(dirname "$0")" && pwd)
module_dir=$(CDPATH= cd "$case_dir/../../.." && pwd)
run_dir=$(mktemp -d)
echo "Local run: $run_dir"
git init -q "$run_dir/repo"
git -C "$run_dir/repo" fetch -q --depth=1 https://github.com/pallets/click.git refs/pull/3902/head
git -C "$run_dir/repo" checkout -q --detach FETCH_HEAD
plan_digest=$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$case_dir/plan.json")
python3 "$module_dir/skills/project-test/scripts/project_test.py" native-tox \
    --repo "$run_dir/repo" --plan "$case_dir/plan.json" --plan-sha256 "$plan_digest" --out "$run_dir/result"
echo "Local report: $run_dir/result/report.json"
