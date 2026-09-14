package com.apibridge.apibridge.model;

public record DiffRequest(
        String v1Spec,
        String v2Spec
) {
}
