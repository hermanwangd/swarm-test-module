# Company Swarm — standalone import and version pinning

## Build and test

Requirements: JDK 17+, Maven 3.9+, and access to the approved dependency mirror.

```bash
mvn -B -ntp verify
mvn -B -ntp -DskipTests install
mvn -B -ntp -f examples/company-swarm-consumer/pom.xml test
```

A successful independent consumer test proves the public library classes and ServiceLoader registration work without any `engcim-swarm` source tree. It does **not** prove real SIT, E2E, or downstream deployment.

## Import from a company package registry

Publish the standard (non-`cli`) artifact to an approved internal Maven Registry, retaining this POM coordinate:

```xml
<dependency>
  <groupId>com.featuredeliveryintelligence</groupId>
  <artifactId>swarm-product-test</artifactId>
  <version>1.0.0</version>
</dependency>
```

Register the company's credentials, repository URL and artifact permissions in the consumer's Maven settings or dependency-management configuration; never commit credentials. Prefer a fixed version and immutable artifact checksum. Do not use `SNAPSHOT` for company-wide imports.

## Runtime dependency

The module intentionally does not depend on framework source. Supply the trusted Framework JAR and independently verified SHA-256 through host configuration, as described in [README](../README.md). Call the exposed `product-test run --request <request.json>` CLI or `ProductTestingModules.resolve(...)` API.

Only the current local and explicitly supported integration slices are claimed. Real RP SIT, Cross-RP E2E and release promotion require separate runtime evidence and policy gates.

## GitHub Packages publication

The owner changed the delivery condition to **public** on 2026-11-21. The target is
`hermanwangd/swarm-test-module`, with Maven URL
`https://maven.pkg.github.com/hermanwangd/swarm-test-module` and server ID
`internal-maven`. The `internal-publish.yml` workflow publishes only from tag
`v1.0.0` in that independent repository. It checks the root commit,
verifies tests, retains source/CI/JAR pins, and refuses any existing POM or JAR
for that version. GitHub Packages supplies the server-side no-overwrite
boundary; never delete/recreate a released version to bypass it. A partial
publication must use a deliberate subsequent version after investigation.

The workflow uses its repository-scoped `GITHUB_TOKEN` with `packages: write`.
Other Swarm consumers need independently provisioned read access; do not copy
the producer token. Credentials belong in private Maven settings under server
`internal-maven`. No credentials or driver binaries are included in the package.

To verify an independently approved artifact using a new project and empty
Maven cache:

```sh
bash scripts/verify-registry-consumer.sh \
  https://maven.pkg.github.com/hermanwangd/swarm-test-module \
  APPROVED_MODULE_JAR_SHA256 /absolute/new-consumer-evidence
```

Maven reads ordinary user settings (or `MAVEN_ARGS='-s /private/settings.xml'`).
The script first resolves dependencies, checks the supplied SHA-256 and Maven
registry origin, then runs the consumer tests. Its `file://` mode is solely a
local packaging/transport regression. A local file registry is not proof of
GitHub registry publication or another company's access.
