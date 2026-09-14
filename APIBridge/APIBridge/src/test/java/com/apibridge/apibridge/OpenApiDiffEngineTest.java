package com.apibridge.apibridge;

import com.apibridge.apibridge.diff.OpenApiDiffEngine;
import com.apibridge.apibridge.model.BreakingChange;
import com.apibridge.apibridge.model.BreakingChangeReport;
import com.apibridge.apibridge.model.ChangeType;
import com.apibridge.apibridge.parser.OpenApiParserService;
import io.swagger.v3.oas.models.OpenAPI;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class OpenApiDiffEngineTest {

    private OpenApiParserService parserService;
    private OpenApiDiffEngine diffEngine;

    @BeforeEach
    void setUp() {
        parserService = new OpenApiParserService();
        diffEngine = new OpenApiDiffEngine();
    }

    private String loadResource(String path) throws IOException {
        try (InputStream in = getClass().getResourceAsStream(path)) {
            if (in == null) {
                throw new IllegalArgumentException("Resource not found: " + path);
            }
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    @Test
    @DisplayName("Verify structural diff against sample v1 and v2 specifications")
    void testSampleSpecsComparison() throws IOException {
        String v1Json = loadResource("/specs/sample-v1.json");
        String v2Json = loadResource("/specs/sample-v2.json");

        OpenAPI v1 = parserService.parse(v1Json);
        OpenAPI v2 = parserService.parse(v2Json);

        BreakingChangeReport report = diffEngine.compare(v1, v2);

        assertThat(report).isNotNull();
        assertThat(report.totalBreakingChanges()).isEqualTo(7);

        List<BreakingChange> changes = report.breakingChanges();

        // 1. Verify REQUEST_FIELD_REMOVED for 'name'
        assertThat(changes).anySatisfy(c -> {
            assertThat(c.type()).isEqualTo(ChangeType.REQUEST_FIELD_REMOVED);
            assertThat(c.path()).isEqualTo("/api/users");
            assertThat(c.method()).isEqualTo("POST");
            assertThat(c.element()).isEqualTo("name");
        });

        // 2. Verify REQUEST_FIELD_REQUIRED_ADDED for 'username'
        assertThat(changes).anySatisfy(c -> {
            assertThat(c.type()).isEqualTo(ChangeType.REQUEST_FIELD_REQUIRED_ADDED);
            assertThat(c.path()).isEqualTo("/api/users");
            assertThat(c.method()).isEqualTo("POST");
            assertThat(c.element()).isEqualTo("username");
        });

        // 3. Verify RESPONSE_FIELD_REMOVED for 'status'
        assertThat(changes).anySatisfy(c -> {
            assertThat(c.type()).isEqualTo(ChangeType.RESPONSE_FIELD_REMOVED);
            assertThat(c.path()).isEqualTo("/api/users");
            assertThat(c.method()).isEqualTo("POST");
            assertThat(c.element()).isEqualTo("status");
        });

        // 4. Verify PARAMETER_REMOVED for 'includeDetails'
        assertThat(changes).anySatisfy(c -> {
            assertThat(c.type()).isEqualTo(ChangeType.PARAMETER_REMOVED);
            assertThat(c.path()).isEqualTo("/api/users/{id}");
            assertThat(c.method()).isEqualTo("GET");
            assertThat(c.element()).isEqualTo("includeDetails");
        });

        // 5. Verify PARAMETER_REQUIRED_ADDED for 'token'
        assertThat(changes).anySatisfy(c -> {
            assertThat(c.type()).isEqualTo(ChangeType.PARAMETER_REQUIRED_ADDED);
            assertThat(c.path()).isEqualTo("/api/users/{id}");
            assertThat(c.method()).isEqualTo("GET");
            assertThat(c.element()).isEqualTo("token");
        });

        // 6. Verify RESPONSE_FIELD_TYPE_CHANGED for 'name'
        assertThat(changes).anySatisfy(c -> {
            assertThat(c.type()).isEqualTo(ChangeType.RESPONSE_FIELD_TYPE_CHANGED);
            assertThat(c.path()).isEqualTo("/api/users/{id}");
            assertThat(c.method()).isEqualTo("GET");
            assertThat(c.element()).isEqualTo("name");
            assertThat(c.v1Value()).isEqualTo("string");
            assertThat(c.v2Value()).isEqualTo("integer");
        });

        // 7. Verify METHOD_REMOVED for 'DELETE'
        assertThat(changes).anySatisfy(c -> {
            assertThat(c.type()).isEqualTo(ChangeType.METHOD_REMOVED);
            assertThat(c.path()).isEqualTo("/api/users/{id}");
            assertThat(c.method()).isEqualTo("DELETE");
        });

        // Verify non-breaking changes are NOT in the report
        assertThat(changes).noneMatch(c -> "nickname".equals(c.element()));
        assertThat(changes).noneMatch(c -> "createdAt".equals(c.element()));
        assertThat(changes).noneMatch(c -> "filter".equals(c.element()));
        assertThat(changes).noneMatch(c -> "/api/users/archived".equals(c.path()));
        assertThat(changes).noneMatch(c -> "/api/users".equals(c.path()) && "GET".equals(c.method()));
    }

    @Test
    @DisplayName("Verify structural separation: removal and addition reported independently without rename assumption")
    void testStructuralIndependence() {
        String v1Spec = """
                {
                  "openapi": "3.0.0",
                  "info": { "title": "Test", "version": "1.0.0" },
                  "paths": {
                    "/profile": {
                      "post": {
                        "requestBody": {
                          "required": true,
                          "content": {
                            "application/json": {
                              "schema": {
                                "type": "object",
                                "properties": {
                                  "name": { "type": "string" }
                                }
                              }
                            }
                          }
                        },
                        "responses": { "200": { "description": "ok" } }
                      }
                    }
                  }
                }
                """;

        String v2Spec = """
                {
                  "openapi": "3.0.0",
                  "info": { "title": "Test", "version": "2.0.0" },
                  "paths": {
                    "/profile": {
                      "post": {
                        "requestBody": {
                          "required": true,
                          "content": {
                            "application/json": {
                              "schema": {
                                "type": "object",
                                "required": ["username"],
                                "properties": {
                                  "username": { "type": "string" }
                                }
                              }
                            }
                          }
                        },
                        "responses": { "200": { "description": "ok" } }
                      }
                    }
                  }
                }
                """;

        OpenAPI v1 = parserService.parse(v1Spec);
        OpenAPI v2 = parserService.parse(v2Spec);

        BreakingChangeReport report = diffEngine.compare(v1, v2);

        // Exactly 2 changes: 'name' removed, 'username' newly required
        assertThat(report.totalBreakingChanges()).isEqualTo(2);

        assertThat(report.breakingChanges()).anySatisfy(c -> {
            assertThat(c.type()).isEqualTo(ChangeType.REQUEST_FIELD_REMOVED);
            assertThat(c.element()).isEqualTo("name");
            assertThat(c.description()).doesNotContainIgnoringCase("rename");
        });

        assertThat(report.breakingChanges()).anySatisfy(c -> {
            assertThat(c.type()).isEqualTo(ChangeType.REQUEST_FIELD_REQUIRED_ADDED);
            assertThat(c.element()).isEqualTo("username");
            assertThat(c.description()).doesNotContainIgnoringCase("rename");
        });
    }

    @Test
    @DisplayName("Verify removed endpoint is detected as breaking change")
    void testEndpointRemoved() {
        String v1Spec = """
                {
                  "openapi": "3.0.0",
                  "info": { "title": "Test", "version": "1.0.0" },
                  "paths": {
                    "/legacy": {
                      "get": { "responses": { "200": { "description": "ok" } } }
                    }
                  }
                }
                """;

        String v2Spec = """
                {
                  "openapi": "3.0.0",
                  "info": { "title": "Test", "version": "2.0.0" },
                  "paths": {}
                }
                """;

        OpenAPI v1 = parserService.parse(v1Spec);
        OpenAPI v2 = parserService.parse(v2Spec);

        BreakingChangeReport report = diffEngine.compare(v1, v2);

        assertThat(report.totalBreakingChanges()).isEqualTo(1);
        BreakingChange bc = report.breakingChanges().getFirst();
        assertThat(bc.type()).isEqualTo(ChangeType.ENDPOINT_REMOVED);
        assertThat(bc.path()).isEqualTo("/legacy");
    }
}
