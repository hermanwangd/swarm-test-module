package company.swarm;

import com.featuredeliveryintelligence.fdi.producttest.ProductTestingModuleProvider;
import com.featuredeliveryintelligence.fdi.producttest.ProductTestingModules;
import com.featuredeliveryintelligence.fdi.producttest.ProductTestRequest;
import com.featuredeliveryintelligence.fdi.producttest.ProductTestReceipt;
import java.util.Map;
import java.util.ServiceLoader;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

final class ModuleImportTest {
    @Test
    void importedModuleRejectsUnsupportedSitBeforeCallingTheFramework() {
        var module = ProductTestingModules.resolve("product-test", "1",
                request -> { throw new AssertionError("SIT must never dispatch"); },
                Thread.currentThread().getContextClassLoader());
        var request = new ProductTestRequest("product-test-request.v1", "product-test", "1",
                "consumer-mission", "consumer-request", "rev-1", "workspace", "project",
                Map.of(), Map.of(), "integration", "regression", "sit", "not_used",
                "/unread", "/unread/suite.yaml", "suite", "profile", "/unread/handoff.json", "0".repeat(64));
        var receipt = module.execute(request);
        assertEquals(ProductTestReceipt.Outcome.REJECTED, receipt.outcome());
        assertTrue(receipt.diagnostic().contains("Unsupported capability"));
        assertFalse(receipt.releaseEvidenceEligible());
        assertTrue(receipt.frameworkVerdict().isEmpty());
    }

    @Test
    void aCleanConsumerCanImportAndDiscoverTheModuleWithoutSwarmHostSources() {
        var providers = ServiceLoader.load(ProductTestingModuleProvider.class)
                .stream().map(ServiceLoader.Provider::get).toList();
        assertEquals(1, providers.size(), "The default combined JAR should register one provider");
        assertEquals("product-test", providers.get(0).id());
        assertEquals("1", providers.get(0).version());

        var module = ProductTestingModules.resolve(
                "product-test", "1",
                request -> { throw new AssertionError("Import-only test must not execute a framework"); },
                Thread.currentThread().getContextClassLoader());
        assertEquals("product-test", module.id());
        assertEquals("1", module.version());
    }
}
