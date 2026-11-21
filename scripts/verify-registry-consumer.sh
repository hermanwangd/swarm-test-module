#!/usr/bin/env bash
# Uses a new consumer project AND Maven cache. Never installs the producer locally.
set -euo pipefail
if [ "$#" -ne 3 ]; then
  echo 'usage: verify-registry-consumer.sh REGISTRY_URL EXPECTED_JAR_SHA256 NEW_OUTPUT_DIR' >&2
  exit 2
fi
registry=$1
expected=$2
case "$registry" in https://*|file://*) ;; *) echo 'Registry must use HTTPS (file:// only for local transport tests)' >&2; exit 2;; esac
[[ "$expected" =~ ^[0-9a-f]{64}$ ]] || { echo 'Invalid SHA-256' >&2; exit 2; }
module=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
mkdir -- "$3"
work=$(cd -- "$3" && pwd -P)
mkdir "$work/consumer"
cp "$module/examples/company-swarm-consumer/pom.xml" "$work/consumer/"
cp -R "$module/examples/company-swarm-consumer/src" "$work/consumer/"
args=(-B -ntp -f "$work/consumer/pom.xml" "-Dmaven.repo.local=$work/repository" "-Dswarm.test.repository.url=$registry")
mvn "${args[@]}" org.apache.maven.plugins:maven-dependency-plugin:3.8.1:resolve > "$work/resolve.log" 2>&1
artifact="$work/repository/com/featuredeliveryintelligence/swarm-product-test/1.0.0/swarm-product-test-1.0.0.jar"
printf '%s  %s\n' "$expected" "$artifact" | sha256sum -c -
grep -q 'swarm-product-test-1.0.0.jar>internal-maven=' "$(dirname "$artifact")/_remote.repositories"
mvn "${args[@]}" test > "$work/test.log" 2>&1
cp "$work/consumer/target/surefire-reports/TEST-company.swarm.ModuleImportTest.xml" "$work/consumer-test.xml"
printf '%s  swarm-product-test-1.0.0.jar\n' "$expected" > "$work/resolved-checksum.sha256"
echo "Fresh registry consumer PASS; evidence: $work"
