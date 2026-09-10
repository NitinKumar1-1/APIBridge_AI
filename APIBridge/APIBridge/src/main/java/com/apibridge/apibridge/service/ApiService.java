package com.apibridge.apibridge.service;

import org.springframework.stereotype.Service;

@Service
public class ApiService {

    public String getMessage() {
        return "Hello from APIBridge Service!";
    }
}