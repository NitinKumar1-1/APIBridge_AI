package com.apibridge.apibridge.model;

import java.util.List;

public record BreakingChangeReport(
        String v1Title,
        String v1Version,
        String v2Title,
        String v2Version,
        int totalBreakingChanges,
        List<BreakingChange> breakingChanges
) {
}
