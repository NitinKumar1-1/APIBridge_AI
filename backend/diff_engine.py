"""APIBridge AI - Deterministic OpenAPI Structural Diff Engine

Parses, validates, resolves internal $ref pointers, and compares OpenAPI v1 and v2
specifications (JSON or YAML) to detect breaking and non-breaking changes.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import copy
import json
import yaml
from pydantic import BaseModel, Field


class ChangeCategory(str, Enum):
    BREAKING = "BREAKING"
    NON_BREAKING = "NON_BREAKING"


class ChangeDetail(BaseModel):
    id: str = Field(description="Unique deterministic identifier for this change")
    category: ChangeCategory = Field(description="Classification: BREAKING or NON_BREAKING")
    change_type: str = Field(description="Machine-readable change type identifier")
    path: Optional[str] = Field(default=None, description="API path where change occurred")
    method: Optional[str] = Field(default=None, description="HTTP method if applicable")
    location: str = Field(description="Structural location in the OpenAPI spec")
    description: str = Field(description="Human-readable description of what changed")
    breaking_reason: Optional[str] = Field(
        default=None, description="Explanation of why this change breaks existing clients"
    )
    v1_value: Optional[Any] = Field(default=None, description="Original value in v1")
    v2_value: Optional[Any] = Field(default=None, description="Modified value in v2")


class DiffSummary(BaseModel):
    total_changes: int
    breaking_count: int
    non_breaking_count: int
    is_compatible: bool
    v1_title: Optional[str] = None
    v1_version: Optional[str] = None
    v2_title: Optional[str] = None
    v2_version: Optional[str] = None
    changes: List[ChangeDetail]
    summary_message: str


class DiffRequest(BaseModel):
    spec_v1: str = Field(description="OpenAPI specification v1 in JSON or YAML string")
    spec_v2: str = Field(description="OpenAPI specification v2 in JSON or YAML string")


class OpenAPIDiffEngine:
    """Deterministic structural diff engine for OpenAPI 3.x and Swagger 2.0 specs."""

    HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}

    def __init__(self):
        self.change_counter = 0

    def _next_id(self) -> str:
        self.change_counter += 1
        return f"CHG-{self.change_counter:04d}"

    def parse_and_validate(self, raw_content: str, spec_label: str = "Spec") -> Dict[str, Any]:
        """Safely parse JSON or YAML OpenAPI specification."""
        if not raw_content or not raw_content.strip():
            raise ValueError(f"{spec_label} is empty. Please provide a valid JSON or YAML document.")

        parsed = None
        # Try JSON first
        try:
            parsed = json.loads(raw_content)
        except Exception:
            pass

        # Try YAML if JSON failed
        if parsed is None:
            try:
                parsed = yaml.safe_load(raw_content)
            except Exception as e:
                raise ValueError(
                    f"{spec_label} could not be parsed as valid JSON or YAML: {str(e)}"
                )

        if not isinstance(parsed, dict):
            raise ValueError(f"{spec_label} root must be a valid JSON/YAML object/dictionary.")

        # Check for OpenAPI or Swagger structure
        is_openapi = "openapi" in parsed
        is_swagger = "swagger" in parsed
        has_paths = "paths" in parsed

        if not (is_openapi or is_swagger) and not has_paths:
            raise ValueError(
                f"{spec_label} is missing required OpenAPI structure ('openapi'/'swagger' or 'paths' field)."
            )

        return parsed

    def resolve_references(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively resolves internal $ref pointers (e.g. #/components/schemas/User).

        Guards against circular references.
        """
        root = copy.deepcopy(spec)

        def get_by_json_pointer(pointer: str, current_root: Dict[str, Any]) -> Any:
            if not pointer.startswith("#/"):
                return None
            parts = pointer[2:].split("/")
            node = current_root
            for part in parts:
                part = part.replace("~1", "/").replace("~0", "~")
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    return None
            return node

        def resolve_node(node: Any, seen_refs: Set[str]) -> Any:
            if isinstance(node, dict):
                if "$ref" in node and isinstance(node["$ref"], str):
                    ref = node["$ref"]
                    if ref in seen_refs:
                        # Circular reference detected; return copy with $ref annotation to prevent infinite recursion
                        return {"_circular_ref": ref}
                    target = get_by_json_pointer(ref, root)
                    if target is not None:
                        new_seen = seen_refs | {ref}
                        resolved_target = resolve_node(copy.deepcopy(target), new_seen)
                        # Merge any overrides alongside the resolved target
                        overrides = {k: resolve_node(v, new_seen) for k, v in node.items() if k != "$ref"}
                        if isinstance(resolved_target, dict):
                            resolved_target.update(overrides)
                            return resolved_target
                        return resolved_target
                return {k: resolve_node(v, seen_refs) for k, v in node.items()}
            elif isinstance(node, list):
                return [resolve_node(item, seen_refs) for item in node]
            return node

        return resolve_node(root, set())

    def compare(self, spec_v1_raw: str, spec_v2_raw: str) -> DiffSummary:
        """Executes full deterministic structural comparison between v1 and v2."""
        self.change_counter = 0
        doc1 = self.parse_and_validate(spec_v1_raw, "Specification v1")
        doc2 = self.parse_and_validate(spec_v2_raw, "Specification v2")

        deref_v1 = self.resolve_references(doc1)
        deref_v2 = self.resolve_references(doc2)

        changes: List[ChangeDetail] = []

        v1_info = deref_v1.get("info", {}) if isinstance(deref_v1.get("info"), dict) else {}
        v2_info = deref_v2.get("info", {}) if isinstance(deref_v2.get("info"), dict) else {}

        paths_v1: Dict[str, Any] = deref_v1.get("paths", {}) or {}
        paths_v2: Dict[str, Any] = deref_v2.get("paths", {}) or {}

        # 1. Compare Paths
        for path_key in paths_v1:
            if path_key not in paths_v2:
                changes.append(
                    ChangeDetail(
                        id=self._next_id(),
                        category=ChangeCategory.BREAKING,
                        change_type="PATH_REMOVED",
                        path=path_key,
                        location=f"paths['{path_key}']",
                        description=f"Path '{path_key}' was removed in v2.",
                        breaking_reason=f"Existing clients sending requests to '{path_key}' will receive HTTP 404 Not Found.",
                        v1_value=path_key,
                        v2_value=None,
                    )
                )
            else:
                # Path exists in both, compare operations
                path_obj_v1 = paths_v1[path_key] or {}
                path_obj_v2 = paths_v2[path_key] or {}
                self._compare_path_operations(path_key, path_obj_v1, path_obj_v2, changes)

        for path_key in paths_v2:
            if path_key not in paths_v1:
                changes.append(
                    ChangeDetail(
                        id=self._next_id(),
                        category=ChangeCategory.NON_BREAKING,
                        change_type="PATH_ADDED",
                        path=path_key,
                        location=f"paths['{path_key}']",
                        description=f"New path '{path_key}' was added in v2.",
                        breaking_reason=None,
                        v1_value=None,
                        v2_value=path_key,
                    )
                )

        breaking_count = sum(1 for c in changes if c.category == ChangeCategory.BREAKING)
        non_breaking_count = sum(1 for c in changes if c.category == ChangeCategory.NON_BREAKING)
        is_compatible = breaking_count == 0

        if is_compatible:
            if non_breaking_count == 0:
                summary_msg = "Specifications are structurally identical. Full backward compatibility."
            else:
                summary_msg = f"Specifications are backward-compatible with {non_breaking_count} non-breaking addition(s)."
        else:
            summary_msg = f"Detected {breaking_count} breaking change(s) and {non_breaking_count} non-breaking change(s). Existing clients require mediation."

        v1_title = str(v1_info["title"]) if "title" in v1_info and v1_info["title"] is not None else None
        v1_version = str(v1_info["version"]) if "version" in v1_info and v1_info["version"] is not None else None
        v2_title = str(v2_info["title"]) if "title" in v2_info and v2_info["title"] is not None else None
        v2_version = str(v2_info["version"]) if "version" in v2_info and v2_info["version"] is not None else None

        return DiffSummary(
            total_changes=len(changes),
            breaking_count=breaking_count,
            non_breaking_count=non_breaking_count,
            is_compatible=is_compatible,
            v1_title=v1_title,
            v1_version=v1_version,
            v2_title=v2_title,
            v2_version=v2_version,
            changes=changes,
            summary_message=summary_msg,
        )

    def _compare_path_operations(
        self,
        path: str,
        path_v1: Dict[str, Any],
        path_v2: Dict[str, Any],
        changes: List[ChangeDetail],
    ) -> None:
        """Compares methods (GET, POST, etc.) on an existing path."""
        # Check path-level parameters
        path_params_v1 = path_v1.get("parameters", []) or []
        path_params_v2 = path_v2.get("parameters", []) or []

        methods_v1 = {k.lower(): v for k, v in path_v1.items() if k.lower() in self.HTTP_METHODS}
        methods_v2 = {k.lower(): v for k, v in path_v2.items() if k.lower() in self.HTTP_METHODS}

        for method in methods_v1:
            if method not in methods_v2:
                changes.append(
                    ChangeDetail(
                        id=self._next_id(),
                        category=ChangeCategory.BREAKING,
                        change_type="METHOD_REMOVED",
                        path=path,
                        method=method.upper(),
                        location=f"paths['{path}'].{method}",
                        description=f"HTTP method '{method.upper()}' on '{path}' was removed in v2.",
                        breaking_reason=f"Existing clients sending {method.upper()} to '{path}' will receive HTTP 405 Method Not Allowed.",
                        v1_value=method.upper(),
                        v2_value=None,
                    )
                )
            else:
                # Compare method operation details
                op_v1 = methods_v1[method] or {}
                op_v2 = methods_v2[method] or {}
                self._compare_operation(
                    path, method.upper(), op_v1, op_v2, path_params_v1, path_params_v2, changes
                )

        for method in methods_v2:
            if method not in methods_v1:
                changes.append(
                    ChangeDetail(
                        id=self._next_id(),
                        category=ChangeCategory.NON_BREAKING,
                        change_type="METHOD_ADDED",
                        path=path,
                        method=method.upper(),
                        location=f"paths['{path}'].{method}",
                        description=f"New HTTP method '{method.upper()}' on '{path}' was added in v2.",
                        breaking_reason=None,
                        v1_value=None,
                        v2_value=method.upper(),
                    )
                )

    def _compare_operation(
        self,
        path: str,
        method: str,
        op_v1: Dict[str, Any],
        op_v2: Dict[str, Any],
        path_params_v1: List[Any],
        path_params_v2: List[Any],
        changes: List[ChangeDetail],
    ) -> None:
        """Compares operation parameters, requestBody, and responses."""
        # 1. Compare Parameters (merge path-level with operation-level)
        params_v1_list = list(path_params_v1) + (op_v1.get("parameters", []) or [])
        params_v2_list = list(path_params_v2) + (op_v2.get("parameters", []) or [])

        self._compare_parameters(path, method, params_v1_list, params_v2_list, changes)

        # 2. Compare Request Body
        self._compare_request_body(path, method, op_v1, op_v2, changes)

        # 3. Compare Responses
        self._compare_responses(path, method, op_v1.get("responses", {}) or {}, op_v2.get("responses", {}) or {}, changes)

    def _compare_parameters(
        self,
        path: str,
        method: str,
        params_v1: List[Any],
        params_v2: List[Any],
        changes: List[ChangeDetail],
    ) -> None:
        """Compares request parameters (query, header, path, cookie)."""
        map_v1: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for p in params_v1:
            if isinstance(p, dict) and "name" in p:
                p_in = p.get("in", "query")
                map_v1[(p["name"], p_in)] = p

        map_v2: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for p in params_v2:
            if isinstance(p, dict) and "name" in p:
                p_in = p.get("in", "query")
                map_v2[(p["name"], p_in)] = p

        # Check removed parameters
        for (name, p_in), p1 in map_v1.items():
            if (name, p_in) not in map_v2:
                # If optional parameter was removed, server usually ignores it (NON_BREAKING)
                # If path param was removed, the entire path template changed
                changes.append(
                    ChangeDetail(
                        id=self._next_id(),
                        category=ChangeCategory.NON_BREAKING,
                        change_type="PARAM_REMOVED",
                        path=path,
                        method=method,
                        location=f"{method} {path}.parameters.{p_in}.{name}",
                        description=f"Parameter '{name}' (in: {p_in}) was removed in v2.",
                        breaking_reason=None,
                        v1_value=p1.get("required", False),
                        v2_value=None,
                    )
                )

        # Check added and modified parameters
        for (name, p_in), p2 in map_v2.items():
            req2 = bool(p2.get("required", False))
            type2 = self._extract_schema_type(p2.get("schema", p2))

            if (name, p_in) not in map_v1:
                if req2:
                    changes.append(
                        ChangeDetail(
                            id=self._next_id(),
                            category=ChangeCategory.BREAKING,
                            change_type="PARAM_REQUIRED_ADDED",
                            path=path,
                            method=method,
                            location=f"{method} {path}.parameters.{p_in}.{name}",
                            description=f"New required parameter '{name}' (in: {p_in}) added in v2.",
                            breaking_reason=f"Existing clients do not send '{name}' and will receive HTTP 400 Bad Request.",
                            v1_value=None,
                            v2_value={"name": name, "in": p_in, "required": True},
                        )
                    )
                else:
                    changes.append(
                        ChangeDetail(
                            id=self._next_id(),
                            category=ChangeCategory.NON_BREAKING,
                            change_type="PARAM_OPTIONAL_ADDED",
                            path=path,
                            method=method,
                            location=f"{method} {path}.parameters.{p_in}.{name}",
                            description=f"New optional parameter '{name}' (in: {p_in}) added in v2.",
                            breaking_reason=None,
                            v1_value=None,
                            v2_value={"name": name, "in": p_in, "required": False},
                        )
                    )
            else:
                # Parameter in both, check if required state changed or type changed
                p1 = map_v1[(name, p_in)]
                req1 = bool(p1.get("required", False))
                type1 = self._extract_schema_type(p1.get("schema", p1))

                if not req1 and req2:
                    changes.append(
                        ChangeDetail(
                            id=self._next_id(),
                            category=ChangeCategory.BREAKING,
                            change_type="PARAM_MADE_REQUIRED",
                            path=path,
                            method=method,
                            location=f"{method} {path}.parameters.{p_in}.{name}.required",
                            description=f"Parameter '{name}' (in: {p_in}) changed from optional to required in v2.",
                            breaking_reason="Old clients that omit this parameter will now be rejected by the server.",
                            v1_value=False,
                            v2_value=True,
                        )
                    )
                elif req1 and not req2:
                    changes.append(
                        ChangeDetail(
                            id=self._next_id(),
                            category=ChangeCategory.NON_BREAKING,
                            change_type="PARAM_MADE_OPTIONAL",
                            path=path,
                            method=method,
                            location=f"{method} {path}.parameters.{p_in}.{name}.required",
                            description=f"Parameter '{name}' (in: {p_in}) changed from required to optional in v2.",
                            breaking_reason=None,
                            v1_value=True,
                            v2_value=False,
                        )
                    )

                if type1 and type2 and type1 != type2:
                    changes.append(
                        ChangeDetail(
                            id=self._next_id(),
                            category=ChangeCategory.BREAKING,
                            change_type="PARAM_TYPE_CHANGED",
                            path=path,
                            method=method,
                            location=f"{method} {path}.parameters.{p_in}.{name}.type",
                            description=f"Parameter '{name}' (in: {p_in}) type changed from '{type1}' to '{type2}'.",
                            breaking_reason=f"Existing client serialization of type '{type1}' will fail schema validation for '{type2}'.",
                            v1_value=type1,
                            v2_value=type2,
                        )
                    )

    def _compare_request_body(
        self,
        path: str,
        method: str,
        op_v1: Dict[str, Any],
        op_v2: Dict[str, Any],
        changes: List[ChangeDetail],
    ) -> None:
        """Compares requestBody specification and payload schemas."""
        rb1 = op_v1.get("requestBody")
        rb2 = op_v2.get("requestBody")

        # Handle Swagger 2.0 body parameter if present
        if not rb1:
            for p in op_v1.get("parameters", []) or []:
                if isinstance(p, dict) and p.get("in") == "body":
                    rb1 = {"content": {"application/json": {"schema": p.get("schema", {})}}, "required": p.get("required", False)}
                    break

        if not rb2:
            for p in op_v2.get("parameters", []) or []:
                if isinstance(p, dict) and p.get("in") == "body":
                    rb2 = {"content": {"application/json": {"schema": p.get("schema", {})}}, "required": p.get("required", False)}
                    break

        if not rb1 and not rb2:
            return

        if rb1 and not rb2:
            # Request body removed in v2
            req1 = rb1.get("required", False) if isinstance(rb1, dict) else False
            changes.append(
                ChangeDetail(
                    id=self._next_id(),
                    category=ChangeCategory.NON_BREAKING if not req1 else ChangeCategory.BREAKING,
                    change_type="REQUEST_BODY_REMOVED",
                    path=path,
                    method=method,
                    location=f"{method} {path}.requestBody",
                    description=f"Request body on '{method} {path}' was removed in v2.",
                    breaking_reason="Clients submitting a request payload may have their data ignored or rejected." if req1 else None,
                    v1_value=bool(req1),
                    v2_value=None,
                )
            )
            return

        if not rb1 and rb2:
            req2 = rb2.get("required", False) if isinstance(rb2, dict) else False
            if req2:
                changes.append(
                    ChangeDetail(
                        id=self._next_id(),
                        category=ChangeCategory.BREAKING,
                        change_type="REQUEST_BODY_REQUIRED_ADDED",
                        path=path,
                        method=method,
                        location=f"{method} {path}.requestBody",
                        description=f"Newly required request body added to '{method} {path}' in v2.",
                        breaking_reason="Existing clients submitting empty requests will receive HTTP 400 or 422.",
                        v1_value=None,
                        v2_value=True,
                    )
                )
            else:
                changes.append(
                    ChangeDetail(
                        id=self._next_id(),
                        category=ChangeCategory.NON_BREAKING,
                        change_type="REQUEST_BODY_OPTIONAL_ADDED",
                        path=path,
                        method=method,
                        location=f"{method} {path}.requestBody",
                        description=f"Optional request body added to '{method} {path}' in v2.",
                        breaking_reason=None,
                        v1_value=None,
                        v2_value=False,
                    )
                )
            return

        # Both have request body
        req1 = rb1.get("required", False) if isinstance(rb1, dict) else False
        req2 = rb2.get("required", False) if isinstance(rb2, dict) else False

        if not req1 and req2:
            changes.append(
                ChangeDetail(
                    id=self._next_id(),
                    category=ChangeCategory.BREAKING,
                    change_type="REQUEST_BODY_MADE_REQUIRED",
                    path=path,
                    method=method,
                    location=f"{method} {path}.requestBody.required",
                    description=f"Request body on '{method} {path}' changed from optional to required in v2.",
                    breaking_reason="Old clients that do not send a request body will now be rejected.",
                    v1_value=False,
                    v2_value=True,
                )
            )

        # Compare application/json schema in requestBody
        content1 = rb1.get("content", {}) if isinstance(rb1, dict) else {}
        content2 = rb2.get("content", {}) if isinstance(rb2, dict) else {}

        schema1 = content1.get("application/json", {}).get("schema", {}) if isinstance(content1, dict) else {}
        schema2 = content2.get("application/json", {}).get("schema", {}) if isinstance(content2, dict) else {}

        if schema1 and schema2:
            self._compare_schemas(
                path=path,
                method=method,
                schema1=schema1,
                schema2=schema2,
                context="requestBody",
                location_prefix=f"{method} {path}.requestBody.schema",
                changes=changes,
            )

    def _compare_responses(
        self,
        path: str,
        method: str,
        resp_v1: Dict[str, Any],
        resp_v2: Dict[str, Any],
        changes: List[ChangeDetail],
    ) -> None:
        """Compares status codes and response schemas."""
        for code in resp_v1:
            if code not in resp_v2:
                # Removing a 2xx or 3xx response is a breaking change
                is_breaking = str(code).startswith("2") or str(code).startswith("3")
                changes.append(
                    ChangeDetail(
                        id=self._next_id(),
                        category=ChangeCategory.BREAKING if is_breaking else ChangeCategory.NON_BREAKING,
                        change_type="RESPONSE_CODE_REMOVED",
                        path=path,
                        method=method,
                        location=f"{method} {path}.responses['{code}']",
                        description=f"Response status code '{code}' on '{method} {path}' was removed in v2.",
                        breaking_reason=(
                            f"Existing clients expecting HTTP {code} on successful operations will encounter unexpected behavior."
                            if is_breaking
                            else None
                        ),
                        v1_value=code,
                        v2_value=None,
                    )
                )
            else:
                # Compare response schemas
                r1_obj = resp_v1[code] or {}
                r2_obj = resp_v2[code] or {}
                s1 = self._get_response_schema(r1_obj)
                s2 = self._get_response_schema(r2_obj)

                if s1 and s2:
                    self._compare_schemas(
                        path=path,
                        method=method,
                        schema1=s1,
                        schema2=s2,
                        context=f"response_{code}",
                        location_prefix=f"{method} {path}.responses['{code}'].schema",
                        changes=changes,
                    )

        for code in resp_v2:
            if code not in resp_v1:
                changes.append(
                    ChangeDetail(
                        id=self._next_id(),
                        category=ChangeCategory.NON_BREAKING,
                        change_type="RESPONSE_CODE_ADDED",
                        path=path,
                        method=method,
                        location=f"{method} {path}.responses['{code}']",
                        description=f"New response status code '{code}' added to '{method} {path}' in v2.",
                        breaking_reason=None,
                        v1_value=None,
                        v2_value=code,
                    )
                )

    def _get_response_schema(self, resp_obj: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts schema from OpenAPI 3.x content or Swagger 2.0 schema."""
        if not isinstance(resp_obj, dict):
            return {}
        content = resp_obj.get("content", {})
        if isinstance(content, dict) and "application/json" in content:
            return content["application/json"].get("schema", {}) or {}
        # Fallback to direct schema (Swagger 2.0)
        return resp_obj.get("schema", {}) or {}

    def _compare_schemas(
        self,
        path: str,
        method: str,
        schema1: Dict[str, Any],
        schema2: Dict[str, Any],
        context: str,
        location_prefix: str,
        changes: List[ChangeDetail],
    ) -> None:
        """Compares two JSON schemas recursively for breaking changes."""
        if not isinstance(schema1, dict) or not isinstance(schema2, dict):
            return

        type1 = self._extract_schema_type(schema1)
        type2 = self._extract_schema_type(schema2)

        if type1 and type2 and type1 != type2:
            changes.append(
                ChangeDetail(
                    id=self._next_id(),
                    category=ChangeCategory.BREAKING,
                    change_type=f"{context.upper()}_TYPE_CHANGED",
                    path=path,
                    method=method,
                    location=f"{location_prefix}.type",
                    description=f"{context.replace('_', ' ').title()} root type changed from '{type1}' to '{type2}'.",
                    breaking_reason=f"Type incompatibility: existing deserializers expecting '{type1}' will fail parsing '{type2}'.",
                    v1_value=type1,
                    v2_value=type2,
                )
            )
            return

        props1 = schema1.get("properties", {}) or {}
        props2 = schema2.get("properties", {}) or {}
        req1_list = set(schema1.get("required", []) or [])
        req2_list = set(schema2.get("required", []) or [])

        is_request = context.startswith("request")
        is_response = context.startswith("response")

        # 1. Properties removed in v2
        for prop_name, p1_schema in props1.items():
            if prop_name not in props2:
                if is_request:
                    # Removed request field: old clients might still submit it
                    changes.append(
                        ChangeDetail(
                            id=self._next_id(),
                            category=ChangeCategory.BREAKING,
                            change_type="REQUEST_BODY_FIELD_REMOVED",
                            path=path,
                            method=method,
                            location=f"{location_prefix}.properties.{prop_name}",
                            description=f"Request body field '{prop_name}' was removed in v2.",
                            breaking_reason=f"Existing client requests sending field '{prop_name}' may be rejected or stripped by the updated API.",
                            v1_value=prop_name,
                            v2_value=None,
                        )
                    )
                elif is_response:
                    # Removed response field: BREAKING for clients expecting it!
                    changes.append(
                        ChangeDetail(
                            id=self._next_id(),
                            category=ChangeCategory.BREAKING,
                            change_type="RESPONSE_FIELD_REMOVED",
                            path=path,
                            method=method,
                            location=f"{location_prefix}.properties.{prop_name}",
                            description=f"Response field '{prop_name}' was removed from {context} in v2.",
                            breaking_reason=f"Existing clients consuming response field '{prop_name}' will encounter null/undefined errors.",
                            v1_value=prop_name,
                            v2_value=None,
                        )
                    )

        # 2. Properties added in v2
        for prop_name, p2_schema in props2.items():
            if prop_name not in props1:
                is_new_req = prop_name in req2_list
                if is_request:
                    if is_new_req:
                        # Newly required request field: BREAKING!
                        changes.append(
                            ChangeDetail(
                                id=self._next_id(),
                                category=ChangeCategory.BREAKING,
                                change_type="REQUEST_BODY_FIELD_REQUIRED_ADDED",
                                path=path,
                                method=method,
                                location=f"{location_prefix}.properties.{prop_name}",
                                description=f"Newly required request field '{prop_name}' added in v2.",
                                breaking_reason=f"Existing client payloads lack '{prop_name}' and will trigger schema validation rejection.",
                                v1_value=None,
                                v2_value=prop_name,
                            )
                        )
                    else:
                        # Optional request field added: NON-BREAKING
                        changes.append(
                            ChangeDetail(
                                id=self._next_id(),
                                category=ChangeCategory.NON_BREAKING,
                                change_type="REQUEST_BODY_FIELD_OPTIONAL_ADDED",
                                path=path,
                                method=method,
                                location=f"{location_prefix}.properties.{prop_name}",
                                description=f"Optional request field '{prop_name}' added in v2.",
                                breaking_reason=None,
                                v1_value=None,
                                v2_value=prop_name,
                            )
                        )
                elif is_response:
                    # New response field: NON-BREAKING (additive change)
                    changes.append(
                        ChangeDetail(
                            id=self._next_id(),
                            category=ChangeCategory.NON_BREAKING,
                            change_type="RESPONSE_FIELD_ADDED",
                            path=path,
                            method=method,
                            location=f"{location_prefix}.properties.{prop_name}",
                            description=f"New response field '{prop_name}' added to {context} in v2.",
                            breaking_reason=None,
                            v1_value=None,
                            v2_value=prop_name,
                        )
                    )

        # 3. Properties present in both: check type and required transitions
        for prop_name in set(props1.keys()) & set(props2.keys()):
            p1_prop = props1[prop_name] or {}
            p2_prop = props2[prop_name] or {}

            p1_type = self._extract_schema_type(p1_prop)
            p2_type = self._extract_schema_type(p2_prop)

            if p1_type and p2_type and p1_type != p2_type:
                changes.append(
                    ChangeDetail(
                        id=self._next_id(),
                        category=ChangeCategory.BREAKING,
                        change_type=f"{context.upper()}_FIELD_TYPE_CHANGED",
                        path=path,
                        method=method,
                        location=f"{location_prefix}.properties.{prop_name}.type",
                        description=f"Field '{prop_name}' in {context} changed type from '{p1_type}' to '{p2_type}'.",
                        breaking_reason=f"Type mismatch: clients expecting '{p1_type}' will fail when processing '{p2_type}'.",
                        v1_value=p1_type,
                        v2_value=p2_type,
                    )
                )

            # Check required transition for request fields
            if is_request:
                was_req = prop_name in req1_list
                is_req = prop_name in req2_list
                if not was_req and is_req:
                    changes.append(
                        ChangeDetail(
                            id=self._next_id(),
                            category=ChangeCategory.BREAKING,
                            change_type="REQUEST_BODY_FIELD_MADE_REQUIRED",
                            path=path,
                            method=method,
                            location=f"{location_prefix}.required.{prop_name}",
                            description=f"Existing request field '{prop_name}' became required in v2.",
                            breaking_reason=f"Existing clients omitting '{prop_name}' will fail validation on the server.",
                            v1_value=False,
                            v2_value=True,
                        )
                    )
                elif was_req and not is_req:
                    changes.append(
                        ChangeDetail(
                            id=self._next_id(),
                            category=ChangeCategory.NON_BREAKING,
                            change_type="REQUEST_BODY_FIELD_MADE_OPTIONAL",
                            path=path,
                            method=method,
                            location=f"{location_prefix}.required.{prop_name}",
                            description=f"Existing request field '{prop_name}' was relaxed from required to optional in v2.",
                            breaking_reason=None,
                            v1_value=True,
                            v2_value=False,
                        )
                    )

            # Recursive comparison for nested object schemas
            if isinstance(p1_prop, dict) and isinstance(p2_prop, dict):
                if p1_type == "object" and p2_type == "object":
                    self._compare_schemas(
                        path=path,
                        method=method,
                        schema1=p1_prop,
                        schema2=p2_prop,
                        context=context,
                        location_prefix=f"{location_prefix}.properties.{prop_name}",
                        changes=changes,
                    )
                elif p1_type == "array" and p2_type == "array":
                    items1 = p1_prop.get("items", {}) or {}
                    items2 = p2_prop.get("items", {}) or {}
                    if isinstance(items1, dict) and isinstance(items2, dict):
                        self._compare_schemas(
                            path=path,
                            method=method,
                            schema1=items1,
                            schema2=items2,
                            context=context,
                            location_prefix=f"{location_prefix}.properties.{prop_name}.items",
                            changes=changes,
                        )

    def _extract_schema_type(self, schema_or_param: Any) -> Optional[str]:
        """Extracts simple type string (string, integer, boolean, array, object)."""
        if not isinstance(schema_or_param, dict):
            return None
        if "type" in schema_or_param and isinstance(schema_or_param["type"], str):
            return schema_or_param["type"]
        if "schema" in schema_or_param and isinstance(schema_or_param["schema"], dict):
            return schema_or_param["schema"].get("type")
        return None
