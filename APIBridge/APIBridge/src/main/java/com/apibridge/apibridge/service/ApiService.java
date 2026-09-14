package com.apibridge.apibridge.service;

import com.apibridge.apibridge.diff.OpenApiDiffEngine;
import com.apibridge.apibridge.model.BreakingChangeReport;
import com.apibridge.apibridge.parser.OpenApiParserService;
import io.swagger.v3.oas.models.OpenAPI;
import org.springframework.stereotype.Service;

@Service
public class ApiService {

    private final OpenApiParserService parserService;
    private final OpenApiDiffEngine diffEngine;

    public ApiService(OpenApiParserService parserService, OpenApiDiffEngine diffEngine) {
        this.parserService = parserService;
        this.diffEngine = diffEngine;
    }

    public String getMessage() {
        return "Hello from APIBridge Service!";
    }

    public BreakingChangeReport generateReport(String v1Spec, String v2Spec) {
        OpenAPI v1 = parserService.parse(v1Spec);
        OpenAPI v2 = parserService.parse(v2Spec);
        return diffEngine.compare(v1, v2);
    }
}