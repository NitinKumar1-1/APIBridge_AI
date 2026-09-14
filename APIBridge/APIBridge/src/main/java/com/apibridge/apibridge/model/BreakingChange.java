package com.apibridge.apibridge.model;

public record BreakingChange(
        String id,
        ChangeType type,
        String path,
        String method,
        String location,
        String element,
        String description,
        String v1Value,
        String v2Value
) {
}
