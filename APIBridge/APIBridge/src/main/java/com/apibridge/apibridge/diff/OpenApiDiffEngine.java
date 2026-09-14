package com.apibridge.apibridge.diff;

import com.apibridge.apibridge.model.BreakingChange;
import com.apibridge.apibridge.model.BreakingChangeReport;
import com.apibridge.apibridge.model.ChangeType;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.Operation;
import io.swagger.v3.oas.models.PathItem;
import io.swagger.v3.oas.models.media.Content;
import io.swagger.v3.oas.models.media.MediaType;
import io.swagger.v3.oas.models.media.Schema;
import io.swagger.v3.oas.models.parameters.Parameter;
import io.swagger.v3.oas.models.parameters.RequestBody;
import io.swagger.v3.oas.models.responses.ApiResponse;
import io.swagger.v3.oas.models.responses.ApiResponses;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;

@Component
public class OpenApiDiffEngine {

    public BreakingChangeReport compare(OpenAPI v1, OpenAPI v2) {
        List<BreakingChange> breakingChanges = new ArrayList<>();
        AtomicInteger counter = new AtomicInteger(1);

        String v1Title = v1.getInfo() != null ? v1.getInfo().getTitle() : "API v1";
        String v1Version = v1.getInfo() != null ? v1.getInfo().getVersion() : "1.0.0";
        String v2Title = v2.getInfo() != null ? v2.getInfo().getTitle() : "API v2";
        String v2Version = v2.getInfo() != null ? v2.getInfo().getVersion() : "2.0.0";

        Map<String, PathItem> v1Paths = v1.getPaths() != null ? v1.getPaths() : Collections.emptyMap();
        Map<String, PathItem> v2Paths = v2.getPaths() != null ? v2.getPaths() : Collections.emptyMap();

        // 1. Path level comparison
        for (Map.Entry<String, PathItem> entry : v1Paths.entrySet()) {
            String path = entry.getKey();
            PathItem v1PathItem = entry.getValue();
            PathItem v2PathItem = v2Paths.get(path);

            if (v2PathItem == null) {
                breakingChanges.add(new BreakingChange(
                        nextId(counter),
                        ChangeType.ENDPOINT_REMOVED,
                        path,
                        "*",
                        "ENDPOINT",
                        path,
                        "Endpoint '" + path + "' was removed in v2.",
                        path,
                        null
                ));
                continue;
            }

            // 2. HTTP Operation level comparison
            comparePathOperations(path, v1PathItem, v2PathItem, breakingChanges, counter);
        }

        return new BreakingChangeReport(
                v1Title,
                v1Version,
                v2Title,
                v2Version,
                breakingChanges.size(),
                breakingChanges
        );
    }

    private void comparePathOperations(String path, PathItem v1PathItem, PathItem v2PathItem,
                                       List<BreakingChange> changes, AtomicInteger counter) {
        Map<PathItem.HttpMethod, Operation> v1Ops = v1PathItem.readOperationsMap();
        Map<PathItem.HttpMethod, Operation> v2Ops = v2PathItem.readOperationsMap();

        if (v1Ops == null) {
            return;
        }

        for (Map.Entry<PathItem.HttpMethod, Operation> entry : v1Ops.entrySet()) {
            PathItem.HttpMethod method = entry.getKey();
            Operation v1Op = entry.getValue();
            Operation v2Op = v2Ops != null ? v2Ops.get(method) : null;

            if (v2Op == null) {
                changes.add(new BreakingChange(
                        nextId(counter),
                        ChangeType.METHOD_REMOVED,
                        path,
                        method.name(),
                        "METHOD",
                        method.name(),
                        "HTTP method '" + method.name() + "' was removed from endpoint '" + path + "'.",
                        method.name(),
                        null
                ));
                continue;
            }

            // 3. Parameters comparison
            compareParameters(path, method.name(), v1Op.getParameters(), v2Op.getParameters(), changes, counter);

            // 4. Request Body comparison
            compareRequestBody(path, method.name(), v1Op.getRequestBody(), v2Op.getRequestBody(), changes, counter);

            // 5. Response comparison
            compareResponses(path, method.name(), v1Op.getResponses(), v2Op.getResponses(), changes, counter);
        }
    }

    private void compareParameters(String path, String method,
                                   List<Parameter> v1ParamsList, List<Parameter> v2ParamsList,
                                   List<BreakingChange> changes, AtomicInteger counter) {
        Map<String, Parameter> v1Params = mapParameters(v1ParamsList);
        Map<String, Parameter> v2Params = mapParameters(v2ParamsList);

        // Check removed parameters and changed parameter types/requirements
        for (Map.Entry<String, Parameter> entry : v1Params.entrySet()) {
            String paramKey = entry.getKey();
            Parameter v1Param = entry.getValue();
            Parameter v2Param = v2Params.get(paramKey);

            String location = (v1Param.getIn() != null ? v1Param.getIn().toUpperCase() : "UNKNOWN") + "_PARAM";

            if (v2Param == null) {
                changes.add(new BreakingChange(
                        nextId(counter),
                        ChangeType.PARAMETER_REMOVED,
                        path,
                        method,
                        location,
                        v1Param.getName(),
                        "Parameter '" + v1Param.getName() + "' (" + v1Param.getIn() + ") was removed in v2.",
                        formatParam(v1Param),
                        null
                ));
            } else {
                // Check if parameter type changed
                String v1Type = resolveSchemaType(v1Param.getSchema());
                String v2Type = resolveSchemaType(v2Param.getSchema());
                if (!Objects.equals(v1Type, v2Type)) {
                    changes.add(new BreakingChange(
                            nextId(counter),
                            ChangeType.PARAMETER_TYPE_CHANGED,
                            path,
                            method,
                            location,
                            v1Param.getName(),
                            "Parameter '" + v1Param.getName() + "' type changed from '" + v1Type + "' to '" + v2Type + "'.",
                            v1Type,
                            v2Type
                    ));
                }

                // Check if parameter became required
                boolean v1Req = Boolean.TRUE.equals(v1Param.getRequired());
                boolean v2Req = Boolean.TRUE.equals(v2Param.getRequired());
                if (!v1Req && v2Req) {
                    changes.add(new BreakingChange(
                            nextId(counter),
                            ChangeType.PARAMETER_REQUIRED_ADDED,
                            path,
                            method,
                            location,
                            v1Param.getName(),
                            "Parameter '" + v1Param.getName() + "' was made required in v2.",
                            "optional",
                            "required"
                    ));
                }
            }
        }

        // Check for newly added parameters that are REQUIRED (breaking for existing clients)
        for (Map.Entry<String, Parameter> entry : v2Params.entrySet()) {
            String paramKey = entry.getKey();
            Parameter v2Param = entry.getValue();
            if (!v1Params.containsKey(paramKey) && Boolean.TRUE.equals(v2Param.getRequired())) {
                String location = (v2Param.getIn() != null ? v2Param.getIn().toUpperCase() : "UNKNOWN") + "_PARAM";
                changes.add(new BreakingChange(
                        nextId(counter),
                        ChangeType.PARAMETER_REQUIRED_ADDED,
                        path,
                        method,
                        location,
                        v2Param.getName(),
                        "New required parameter '" + v2Param.getName() + "' (" + v2Param.getIn() + ") was added in v2.",
                        null,
                        formatParam(v2Param)
                ));
            }
            // Newly added OPTIONAL parameters are non-breaking -> ignored
        }
    }

    private void compareRequestBody(String path, String method,
                                    RequestBody v1Body, RequestBody v2Body,
                                    List<BreakingChange> changes, AtomicInteger counter) {
        if (v1Body == null && v2Body == null) {
            return;
        }

        if (v1Body != null && v2Body == null) {
            changes.add(new BreakingChange(
                    nextId(counter),
                    ChangeType.REQUEST_BODY_REMOVED,
                    path,
                    method,
                    "REQUEST_BODY",
                    "requestBody",
                    "Request body was removed in v2.",
                    "present",
                    null
            ));
            return;
        }

        if (v1Body == null && v2Body != null) {
            if (Boolean.TRUE.equals(v2Body.getRequired())) {
                changes.add(new BreakingChange(
                        nextId(counter),
                        ChangeType.REQUEST_BODY_REQUIRED_ADDED,
                        path,
                        method,
                        "REQUEST_BODY",
                        "requestBody",
                        "A required request body was added in v2.",
                        null,
                        "required"
                ));
            }
            return;
        }

        // Both have request body
        boolean v1Req = Boolean.TRUE.equals(v1Body.getRequired());
        boolean v2Req = Boolean.TRUE.equals(v2Body.getRequired());
        if (!v1Req && v2Req) {
            changes.add(new BreakingChange(
                    nextId(counter),
                    ChangeType.REQUEST_BODY_REQUIRED_ADDED,
                    path,
                    method,
                    "REQUEST_BODY",
                    "requestBody",
                    "Request body was made required in v2.",
                    "optional",
                    "required"
            ));
        }

        Content v1Content = v1Body.getContent();
        Content v2Content = v2Body.getContent();
        if (v1Content == null || v2Content == null) {
            return;
        }

        // Compare schemas for common media types (e.g. application/json)
        for (String mediaType : v1Content.keySet()) {
            MediaType v1Media = v1Content.get(mediaType);
            MediaType v2Media = v2Content.get(mediaType);

            if (v2Media == null) {
                changes.add(new BreakingChange(
                        nextId(counter),
                        ChangeType.REQUEST_BODY_REMOVED,
                        path,
                        method,
                        "REQUEST_BODY",
                        mediaType,
                        "Media type '" + mediaType + "' was removed from request body in v2.",
                        mediaType,
                        null
                ));
                continue;
            }

            compareRequestSchemaProperties(path, method, v1Media.getSchema(), v2Media.getSchema(), changes, counter);
        }
    }

    @SuppressWarnings("rawtypes")
    private void compareRequestSchemaProperties(String path, String method,
                                                Schema v1Schema, Schema v2Schema,
                                                List<BreakingChange> changes, AtomicInteger counter) {
        if (v1Schema == null || v2Schema == null) {
            return;
        }

        Map<String, Schema> v1Props = v1Schema.getProperties() != null ? v1Schema.getProperties() : Collections.emptyMap();
        Map<String, Schema> v2Props = v2Schema.getProperties() != null ? v2Schema.getProperties() : Collections.emptyMap();

        List<String> v1Required = v1Schema.getRequired() != null ? v1Schema.getRequired() : Collections.emptyList();
        List<String> v2Required = v2Schema.getRequired() != null ? v2Schema.getRequired() : Collections.emptyList();

        // 1. Check removed fields from v1 request
        for (Map.Entry<String, Schema> entry : v1Props.entrySet()) {
            String propName = entry.getKey();
            Schema v1Prop = entry.getValue();
            Schema v2Prop = v2Props.get(propName);

            if (v2Prop == null) {
                // Structural removal: field was removed
                changes.add(new BreakingChange(
                        nextId(counter),
                        ChangeType.REQUEST_FIELD_REMOVED,
                        path,
                        method,
                        "REQUEST_BODY",
                        propName,
                        "Request body field '" + propName + "' was removed in v2.",
                        resolveSchemaType(v1Prop),
                        null
                ));
            } else {
                // Field exists in both: check type incompatibility
                String v1Type = resolveSchemaType(v1Prop);
                String v2Type = resolveSchemaType(v2Prop);
                if (!Objects.equals(v1Type, v2Type)) {
                    changes.add(new BreakingChange(
                            nextId(counter),
                            ChangeType.REQUEST_FIELD_TYPE_CHANGED,
                            path,
                            method,
                            "REQUEST_BODY",
                            propName,
                            "Request body field '" + propName + "' type changed from '" + v1Type + "' to '" + v2Type + "'.",
                            v1Type,
                            v2Type
                    ));
                }

                // Check if existing optional field was made required
                if (!v1Required.contains(propName) && v2Required.contains(propName)) {
                    changes.add(new BreakingChange(
                            nextId(counter),
                            ChangeType.REQUEST_FIELD_REQUIRED_ADDED,
                            path,
                            method,
                            "REQUEST_BODY",
                            propName,
                            "Request body field '" + propName + "' was made required in v2.",
                            "optional",
                            "required"
                    ));
                }
            }
        }

        // 2. Check newly added fields in v2 request that are REQUIRED (breaking)
        for (Map.Entry<String, Schema> entry : v2Props.entrySet()) {
            String propName = entry.getKey();
            Schema v2Prop = entry.getValue();

            if (!v1Props.containsKey(propName) && v2Required.contains(propName)) {
                changes.add(new BreakingChange(
                        nextId(counter),
                        ChangeType.REQUEST_FIELD_REQUIRED_ADDED,
                        path,
                        method,
                        "REQUEST_BODY",
                        propName,
                        "New required field '" + propName + "' was added to request body in v2.",
                        null,
                        resolveSchemaType(v2Prop) + " (required)"
                ));
            }
            // Newly added optional fields are non-breaking -> ignored
        }
    }

    private void compareResponses(String path, String method,
                                  ApiResponses v1Responses, ApiResponses v2Responses,
                                  List<BreakingChange> changes, AtomicInteger counter) {
        if (v1Responses == null) {
            return;
        }

        for (Map.Entry<String, ApiResponse> entry : v1Responses.entrySet()) {
            String statusCode = entry.getKey();
            ApiResponse v1Resp = entry.getValue();
            ApiResponse v2Resp = v2Responses != null ? v2Responses.get(statusCode) : null;

            if (v2Resp == null) {
                changes.add(new BreakingChange(
                        nextId(counter),
                        ChangeType.RESPONSE_REMOVED,
                        path,
                        method,
                        "RESPONSE (" + statusCode + ")",
                        statusCode,
                        "Response status code '" + statusCode + "' was removed in v2.",
                        statusCode,
                        null
                ));
                continue;
            }

            Content v1Content = v1Resp.getContent();
            Content v2Content = v2Resp.getContent();
            if (v1Content == null || v2Content == null) {
                continue;
            }

            for (String mediaType : v1Content.keySet()) {
                MediaType v1Media = v1Content.get(mediaType);
                MediaType v2Media = v2Content.get(mediaType);

                if (v2Media == null) {
                    changes.add(new BreakingChange(
                            nextId(counter),
                            ChangeType.RESPONSE_REMOVED,
                            path,
                            method,
                            "RESPONSE (" + statusCode + ")",
                            mediaType,
                            "Response media type '" + mediaType + "' (" + statusCode + ") was removed in v2.",
                            mediaType,
                            null
                    ));
                    continue;
                }

                compareResponseSchemaProperties(path, method, statusCode, v1Media.getSchema(), v2Media.getSchema(), changes, counter);
            }
        }
    }

    @SuppressWarnings("rawtypes")
    private void compareResponseSchemaProperties(String path, String method, String statusCode,
                                                 Schema v1Schema, Schema v2Schema,
                                                 List<BreakingChange> changes, AtomicInteger counter) {
        if (v1Schema == null || v2Schema == null) {
            return;
        }

        Map<String, Schema> v1Props = v1Schema.getProperties() != null ? v1Schema.getProperties() : Collections.emptyMap();
        Map<String, Schema> v2Props = v2Schema.getProperties() != null ? v2Schema.getProperties() : Collections.emptyMap();

        String location = "RESPONSE_BODY (" + statusCode + ")";

        // Check removed fields in response body (Breaking for clients relying on them)
        for (Map.Entry<String, Schema> entry : v1Props.entrySet()) {
            String propName = entry.getKey();
            Schema v1Prop = entry.getValue();
            Schema v2Prop = v2Props.get(propName);

            if (v2Prop == null) {
                changes.add(new BreakingChange(
                        nextId(counter),
                        ChangeType.RESPONSE_FIELD_REMOVED,
                        path,
                        method,
                        location,
                        propName,
                        "Response field '" + propName + "' (" + statusCode + ") was removed in v2.",
                        resolveSchemaType(v1Prop),
                        null
                ));
            } else {
                // Check response field type change
                String v1Type = resolveSchemaType(v1Prop);
                String v2Type = resolveSchemaType(v2Prop);
                if (!Objects.equals(v1Type, v2Type)) {
                    changes.add(new BreakingChange(
                            nextId(counter),
                            ChangeType.RESPONSE_FIELD_TYPE_CHANGED,
                            path,
                            method,
                            location,
                            propName,
                            "Response field '" + propName + "' (" + statusCode + ") type changed from '" + v1Type + "' to '" + v2Type + "'.",
                            v1Type,
                            v2Type
                    ));
                }
            }
        }
        // Newly added fields in response body are non-breaking (extensible clients ignore them) -> omitted
    }

    private Map<String, Parameter> mapParameters(List<Parameter> parameters) {
        if (parameters == null) {
            return Collections.emptyMap();
        }
        Map<String, Parameter> map = new LinkedHashMap<>();
        for (Parameter p : parameters) {
            String key = (p.getIn() != null ? p.getIn().toLowerCase() : "") + ":" + (p.getName() != null ? p.getName() : "");
            map.put(key, p);
        }
        return map;
    }

    @SuppressWarnings("rawtypes")
    private String resolveSchemaType(Schema schema) {
        if (schema == null) {
            return "unknown";
        }
        if (schema.getType() != null) {
            return schema.getType();
        }
        if (schema.getTypes() != null && !schema.getTypes().isEmpty()) {
            return String.join("|", schema.getTypes());
        }
        if (schema.get$ref() != null) {
            return schema.get$ref().substring(schema.get$ref().lastIndexOf('/') + 1);
        }
        return "object";
    }

    private String formatParam(Parameter param) {
        String type = resolveSchemaType(param.getSchema());
        boolean req = Boolean.TRUE.equals(param.getRequired());
        return type + (req ? " (required)" : " (optional)");
    }

    private String nextId(AtomicInteger counter) {
        return String.format("BC-%03d", counter.getAndIncrement());
    }
}
