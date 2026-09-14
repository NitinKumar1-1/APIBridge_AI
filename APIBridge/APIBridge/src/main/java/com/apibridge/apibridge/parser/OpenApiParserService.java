package com.apibridge.apibridge.parser;

import io.swagger.parser.OpenAPIParser;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.parser.core.models.ParseOptions;
import io.swagger.v3.parser.core.models.SwaggerParseResult;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class OpenApiParserService {

    public OpenAPI parse(String specContent) {
        if (specContent == null || specContent.isBlank()) {
            throw new IllegalArgumentException("OpenAPI specification content cannot be null or empty.");
        }

        ParseOptions options = new ParseOptions();
        options.setResolve(true);
        options.setResolveFully(true);

        SwaggerParseResult result = new OpenAPIParser().readContents(specContent, null, options);
        OpenAPI openAPI = result.getOpenAPI();

        if (openAPI == null) {
            List<String> messages = result.getMessages();
            String errorDetails = (messages != null && !messages.isEmpty())
                    ? String.join(", ", messages)
                    : "Invalid OpenAPI specification content.";
            throw new IllegalArgumentException("Failed to parse OpenAPI specification: " + errorDetails);
        }

        return openAPI;
    }
}
