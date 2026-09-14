package com.apibridge.apibridge;

import com.apibridge.apibridge.controller.ApiController;
import com.apibridge.apibridge.diff.OpenApiDiffEngine;
import com.apibridge.apibridge.model.DiffRequest;
import com.apibridge.apibridge.parser.OpenApiParserService;
import com.apibridge.apibridge.service.ApiService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class ApiControllerDiffIntegrationTest {

    private MockMvc mockMvc;
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        OpenApiParserService parserService = new OpenApiParserService();
        OpenApiDiffEngine diffEngine = new OpenApiDiffEngine();
        ApiService apiService = new ApiService(parserService, diffEngine);
        ApiController apiController = new ApiController(apiService);
        this.mockMvc = MockMvcBuilders.standaloneSetup(apiController).build();
        this.objectMapper = new ObjectMapper();
    }

    private String loadResource(String path) throws Exception {
        try (InputStream in = getClass().getResourceAsStream(path)) {
            if (in == null) {
                throw new IllegalArgumentException("Resource not found: " + path);
            }
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    @Test
    @DisplayName("Verify GET /api/hello returns greeting message")
    void testHelloEndpoint() throws Exception {
        mockMvc.perform(get("/api/hello"))
                .andExpect(status().isOk())
                .andExpect(content().string("Hello from APIBridge Service!"));
    }

    @Test
    @DisplayName("Verify POST /api/diff returns BreakingChangeReport")
    void testDiffEndpointSuccess() throws Exception {
        String v1Json = loadResource("/specs/sample-v1.json");
        String v2Json = loadResource("/specs/sample-v2.json");

        DiffRequest request = new DiffRequest(v1Json, v2Json);

        mockMvc.perform(post("/api/diff")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.v1Title").value("User Management API"))
                .andExpect(jsonPath("$.v1Version").value("1.0.0"))
                .andExpect(jsonPath("$.v2Version").value("2.0.0"))
                .andExpect(jsonPath("$.totalBreakingChanges").value(7))
                .andExpect(jsonPath("$.breakingChanges", hasSize(7)))
                .andExpect(jsonPath("$.breakingChanges[*].type", hasItems(
                        "REQUEST_FIELD_REMOVED",
                        "REQUEST_FIELD_REQUIRED_ADDED",
                        "RESPONSE_FIELD_REMOVED",
                        "PARAMETER_REMOVED",
                        "PARAMETER_REQUIRED_ADDED",
                        "RESPONSE_FIELD_TYPE_CHANGED",
                        "METHOD_REMOVED"
                )));
    }

    @Test
    @DisplayName("Verify POST /api/diff returns 400 Bad Request on empty payloads")
    void testDiffEndpointBadRequest() throws Exception {
        DiffRequest request = new DiffRequest(null, null);

        mockMvc.perform(post("/api/diff")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest());
    }
}
