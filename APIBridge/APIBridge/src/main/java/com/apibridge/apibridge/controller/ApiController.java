package com.apibridge.apibridge.controller;

import com.apibridge.apibridge.model.BreakingChangeReport;
import com.apibridge.apibridge.model.DiffRequest;
import com.apibridge.apibridge.service.ApiService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ApiController {

    private final ApiService apiService;

    public ApiController(ApiService apiService) {
        this.apiService = apiService;
    }

    @GetMapping("/api/hello")
    public String hello() {
        return apiService.getMessage();
    }

    @PostMapping("/api/diff")
    public ResponseEntity<BreakingChangeReport> diff(@RequestBody DiffRequest request) {
        if (request == null || request.v1Spec() == null || request.v2Spec() == null) {
            return ResponseEntity.badRequest().build();
        }
        BreakingChangeReport report = apiService.generateReport(request.v1Spec(), request.v2Spec());
        return ResponseEntity.ok(report);
    }
}