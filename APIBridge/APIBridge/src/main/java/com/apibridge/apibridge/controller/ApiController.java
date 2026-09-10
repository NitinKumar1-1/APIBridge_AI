package com.apibridge.apibridge.controller;

import com.apibridge.apibridge.service.ApiService;
import org.springframework.web.bind.annotation.GetMapping;
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
}