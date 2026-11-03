"""APIBridge AI - Intelligent Compatibility Analyzer, Gemini Reasoner,
Transformation Engine, and Fix Validation.

Evaluates contract-level compatibility, uses Google Gemini for root-cause reasoning
and suspected rename discovery, executes safe payload transformations, and validates
fixes against target OpenAPI v2 schemas.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import copy
import json
import os
import re
from pydantic import BaseModel, Field

from diff_engine import ChangeCategory, ChangeDetail, DiffSummary


# ============================================================================
# Enums and Data Models
# ============================================================================

class CompatibilityStatus(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    POTENTIALLY_BREAKING = "POTENTIALLY_BREAKING"
    INCOMPATIBLE = "INCOMPATIBLE"
    INCONCLUSIVE = "INCONCLUSIVE"


class FixStatus(str, Enum):
    NONE = "NONE"
    FIX_GENERATED = "FIX_GENERATED"
    FIX_VALIDATED = "FIX_VALIDATED"
    MANUAL_INTERVENTION_REQUIRED = "MANUAL_INTERVENTION_REQUIRED"


class TransformationActionType(str, Enum):
    RENAME_FIELD = "rename_field"
    MAP_FIELD = "map_field"
    CONVERT_TYPE = "convert_type"
    SPLIT_STRING = "split_string"
    COMBINE_FIELDS = "combine_fields"
    SET_DEFAULT = "set_default"


class TransformationInstruction(BaseModel):
    action: TransformationActionType
    from_field: Optional[str] = None
    to_field: Optional[str] = None
    from_fields: Optional[List[str]] = None
    to_fields: Optional[List[str]] = None
    target_type: Optional[str] = None
    default_value: Optional[Any] = None
    delimiter: Optional[str] = " "
    description: str
    is_safe: bool = True
    manual_intervention_reason: Optional[str] = None


class CompatibilityItem(BaseModel):
    change_id: str
    change_type: str
    location: str
    path: Optional[str] = None
    method: Optional[str] = None
    is_request: bool
    is_response: bool
    compatibility_status: CompatibilityStatus
    compatibility_reason: str
    can_automate_fix: bool
    missing_information: Optional[str] = None
    gemini_explanation: Optional[str] = None
    gemini_impact: Optional[str] = None
    suspected_rename: Optional[str] = None
    suggested_fix: Optional[str] = None
    suggested_transformations: List[TransformationInstruction] = Field(default_factory=list)
    fix_status: FixStatus = FixStatus.NONE


class PayloadValidationResult(BaseModel):
    is_valid: bool
    validation_errors: List[str] = Field(default_factory=list)
    checked_properties: List[str] = Field(default_factory=list)
    notes: str


class CompatibilityAnalysisResponse(BaseModel):
    total_changes: int
    compatible_count: int
    potentially_breaking_count: int
    incompatible_count: int
    inconclusive_count: int
    fixes_generated_count: int
    fixes_validated_count: int
    manual_intervention_count: int
    overall_compatibility: CompatibilityStatus
    summary_message: str
    items: List[CompatibilityItem]
    sample_request_original: Optional[Dict[str, Any]] = None
    sample_request_transformed: Optional[Dict[str, Any]] = None
    payload_validation: Optional[PayloadValidationResult] = None
    ai_provider: str = "none"


class AnalyzeFixesRequest(BaseModel):
    spec_v1: str
    spec_v2: str
    sample_request: Optional[Dict[str, Any]] = None
    target_path: Optional[str] = "/users"
    target_method: Optional[str] = "POST"


# ============================================================================
# 1. Compatibility Analyzer (Contract-Level Rules)
# ============================================================================

def evaluate_change_compatibility(change: ChangeDetail) -> Tuple[CompatibilityStatus, str, bool, Optional[str]]:
    """Evaluates whether a structural change affects backward compatibility.

    Returns:
        (status, reason, can_automate, missing_info)
    """
    ctype = change.change_type
    loc = change.location.lower()
    is_req = "request" in loc or "parameters" in loc or ctype.startswith("PARAM_") or ctype.startswith("REQUEST_")
    is_resp = "response" in loc or ctype.startswith("RESPONSE_")

    # 1. Endpoints & Methods removed: Hard Incompatibility
    if ctype in ("PATH_REMOVED", "METHOD_REMOVED"):
        return (
            CompatibilityStatus.INCOMPATIBLE,
            f"Endpoint or HTTP method was removed. Existing clients sending requests to this route will receive HTTP 404 or 405.",
            False,
            "Target endpoint route is missing in the new service.",
        )

    # 2. Endpoints & Methods added: Compatible
    if ctype in ("PATH_ADDED", "METHOD_ADDED"):
        return (
            CompatibilityStatus.COMPATIBLE,
            "New endpoint or method was added. Existing clients are completely unaffected.",
            False,
            None,
        )

    # 3. Optional Request Additions: Compatible
    if ctype in ("PARAM_OPTIONAL_ADDED", "REQUEST_BODY_FIELD_OPTIONAL_ADDED", "REQUEST_BODY_OPTIONAL_ADDED"):
        return (
            CompatibilityStatus.COMPATIBLE,
            "New optional request field added. Old clients that do not supply this field will be accepted by the server.",
            False,
            None,
        )

    # 4. Response Additions: Compatible for lenient clients
    if ctype in ("RESPONSE_FIELD_ADDED", "RESPONSE_CODE_ADDED"):
        return (
            CompatibilityStatus.COMPATIBLE,
            "New response field or status code added. Compatible for clients that safely ignore unmodeled attributes.",
            False,
            None,
        )

    # 5. Required Request Field Added / Made Required: Potentially Breaking
    if ctype in ("PARAM_REQUIRED_ADDED", "REQUEST_BODY_FIELD_REQUIRED_ADDED", "REQUEST_BODY_FIELD_MADE_REQUIRED", "PARAM_MADE_REQUIRED", "REQUEST_BODY_MADE_REQUIRED"):
        return (
            CompatibilityStatus.POTENTIALLY_BREAKING,
            "A required request field was introduced. Existing clients will fail server schema validation unless a value or default is supplied.",
            True,
            "Requires identifying whether a safe default value exists or if client code must supply new data.",
        )

    # 6. Response Field Removed: Potentially Breaking
    if ctype in ("RESPONSE_FIELD_REMOVED", "RESPONSE_CODE_REMOVED"):
        return (
            CompatibilityStatus.POTENTIALLY_BREAKING,
            "Response field or success code was removed. Clients that read or serialize this attribute may experience runtime null/undefined errors.",
            False,
            "Upstream service no longer computes or returns this response property.",
        )

    # 7. Request Field Removed: Potentially Breaking (Could be a renamed field)
    if ctype in ("REQUEST_BODY_FIELD_REMOVED", "PARAM_REMOVED"):
        return (
            CompatibilityStatus.POTENTIALLY_BREAKING,
            "Request field was removed in v2. The field may have been renamed or refactored into alternative fields.",
            True,
            "Need to determine if the field was renamed, split, or permanently deprecated.",
        )

    # 8. Type Changed: Potentially Breaking / Incompatible
    if "TYPE_CHANGED" in ctype:
        return (
            CompatibilityStatus.POTENTIALLY_BREAKING,
            f"Field data type migrated from '{change.v1_value}' to '{change.v2_value}'. Clients sending or expecting the legacy type will encounter validation or deserialization errors.",
            True,
            f"Requires type casting/conversion between {change.v1_value} and {change.v2_value}.",
        )

    # 9. Optional transitions
    if ctype in ("REQUEST_BODY_FIELD_MADE_OPTIONAL", "PARAM_MADE_OPTIONAL"):
        return (
            CompatibilityStatus.COMPATIBLE,
            "Field requirement was relaxed from required to optional. Old clients providing it remain fully functional.",
            False,
            None,
        )

    return (
        CompatibilityStatus.INCONCLUSIVE,
        "Structural difference detected with indeterminate runtime impact without live schema inspection.",
        False,
        "Insufficient contract context to confirm failure.",
    )


# ============================================================================
# 2. Transformation Engine (Safe, Predefined Python Functions)
# ============================================================================

# Fields considered sensitive/personal user data that must NEVER be invented:
RESTRICTED_PII_KEYWORDS = {
    "address", "phone", "telephone", "mobile", "ssn", "social_security",
    "credit_card", "password", "secret", "national_id", "passport", "dob",
    "birth_date", "identity"
}


def apply_transformations(
    payload: Dict[str, Any],
    transformations: List[TransformationInstruction],
) -> Tuple[Dict[str, Any], List[str]]:
    """Applies a sequence of safe predefined transformations to a request payload.

    Returns:
        (transformed_payload, applied_messages)
    """
    res = copy.deepcopy(payload)
    applied_logs: List[str] = []

    for instr in transformations:
        if not instr.is_safe:
            applied_logs.append(f"SKIPPED (Unsafe): {instr.description}")
            continue

        action = instr.action

        # Action: Rename field
        if action == TransformationActionType.RENAME_FIELD and instr.from_field and instr.to_field:
            if instr.from_field in res:
                val = res.pop(instr.from_field)
                res[instr.to_field] = val
                applied_logs.append(f"Renamed '{instr.from_field}' -> '{instr.to_field}'")

        # Action: Map field (without deleting original if needed, or copy)
        elif action == TransformationActionType.MAP_FIELD and instr.from_field and instr.to_field:
            if instr.from_field in res:
                res[instr.to_field] = res[instr.from_field]
                applied_logs.append(f"Mapped '{instr.from_field}' to '{instr.to_field}'")

        # Action: Convert data type
        elif action == TransformationActionType.CONVERT_TYPE and instr.from_field and instr.target_type:
            target_key = instr.to_field or instr.from_field
            if target_key in res:
                val = res[target_key]
                converted = convert_primitive_type(val, instr.target_type)
                res[target_key] = converted
                applied_logs.append(f"Converted '{target_key}' to {instr.target_type} ({val!r} -> {converted!r})")

        # Action: Split string into multiple fields
        elif action == TransformationActionType.SPLIT_STRING and instr.from_field and instr.to_fields:
            if instr.from_field in res and isinstance(res[instr.from_field], str):
                orig_str = res.pop(instr.from_field)
                delim = instr.delimiter or " "
                parts = orig_str.split(delim)

                if len(instr.to_fields) == 2:
                    res[instr.to_fields[0]] = parts[0] if len(parts) > 0 else ""
                    res[instr.to_fields[1]] = delim.join(parts[1:]) if len(parts) > 1 else ""
                else:
                    for i, target_field in enumerate(instr.to_fields):
                        res[target_field] = parts[i] if i < len(parts) else ""

                applied_logs.append(
                    f"Split '{instr.from_field}' ('{orig_str}') into {instr.to_fields}"
                )

        # Action: Combine multiple fields into one
        elif action == TransformationActionType.COMBINE_FIELDS and instr.from_fields and instr.to_field:
            values_to_join = []
            for f in instr.from_fields:
                if f in res:
                    values_to_join.append(str(res.pop(f)))
            if values_to_join:
                sep = instr.delimiter or " "
                res[instr.to_field] = sep.join(values_to_join)
                applied_logs.append(
                    f"Combined {instr.from_fields} into '{instr.to_field}'"
                )

        # Action: Set safe default value
        elif action == TransformationActionType.SET_DEFAULT and instr.to_field:
            # Enforce safety check: Never invent personal user identity info
            field_lower = instr.to_field.lower()
            if any(pii in field_lower for pii in RESTRICTED_PII_KEYWORDS):
                applied_logs.append(
                    f"REJECTED: Default value for PII field '{instr.to_field}' cannot be automatically generated."
                )
                continue

            if instr.to_field not in res and instr.default_value is not None:
                res[instr.to_field] = instr.default_value
                applied_logs.append(f"Set default for '{instr.to_field}': {instr.default_value!r}")

    return res, applied_logs


def convert_primitive_type(val: Any, target_type: str) -> Any:
    """Safely converts primitive data types."""
    target = target_type.lower()
    if target == "string":
        return str(val) if val is not None else ""
    elif target in ("integer", "int"):
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return 0
    elif target in ("number", "float"):
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0
    elif target in ("boolean", "bool"):
        if isinstance(val, str):
            return val.strip().lower() in ("true", "1", "yes")
        return bool(val)
    return val


# ============================================================================
# 3. Schema Validation Engine
# ============================================================================

def validate_payload_against_schema(
    payload: Dict[str, Any],
    schema: Dict[str, Any],
) -> PayloadValidationResult:
    """Validates a request dictionary against an OpenAPI/JSON schema.

    Checks:
    - Required properties
    - Data types (string, integer, number, boolean, array, object)
    - Nested object schemas
    """
    errors: List[str] = []
    checked_props: List[str] = []

    if not isinstance(schema, dict):
        return PayloadValidationResult(
            is_valid=True,
            validation_errors=[],
            checked_properties=[],
            notes="No formal JSON schema available for verification.",
        )

    # 1. Verify required properties
    required_keys = schema.get("required", []) or []
    for req_key in required_keys:
        checked_props.append(req_key)
        if req_key not in payload:
            errors.append(f"Missing required property '{req_key}'")
        elif payload[req_key] is None:
            errors.append(f"Required property '{req_key}' cannot be null")

    # 2. Verify property types
    properties = schema.get("properties", {}) or {}
    for prop_name, prop_spec in properties.items():
        if prop_name in payload:
            val = payload[prop_name]
            if prop_name not in checked_props:
                checked_props.append(prop_name)

            if val is not None and isinstance(prop_spec, dict):
                expected_type = prop_spec.get("type")
                if expected_type:
                    valid, err = _check_value_type(val, expected_type, prop_name)
                    if not valid and err:
                        errors.append(err)

                # Recursive check for nested objects
                if expected_type == "object" and isinstance(val, dict):
                    nested_res = validate_payload_against_schema(val, prop_spec)
                    errors.extend(nested_res.validation_errors)

    is_valid = len(errors) == 0
    notes = (
        "Payload satisfies the OpenAPI v2 request schema. Note: Schema validity confirms structural adherence; business rule correctness requires runtime API execution."
        if is_valid
        else f"Payload failed schema validation with {len(errors)} error(s)."
    )

    return PayloadValidationResult(
        is_valid=is_valid,
        validation_errors=errors,
        checked_properties=checked_props,
        notes=notes,
    )


def _check_value_type(val: Any, expected_type: str, prop_name: str) -> Tuple[bool, Optional[str]]:
    """Checks whether a value matches the specified OpenAPI schema type."""
    t = expected_type.lower()
    if t == "string":
        if not isinstance(val, str):
            return False, f"Property '{prop_name}' expected string, got {type(val).__name__}"
    elif t in ("integer", "int"):
        if not isinstance(val, int) or isinstance(val, bool):
            return False, f"Property '{prop_name}' expected integer, got {type(val).__name__}"
    elif t in ("number", "float"):
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            return False, f"Property '{prop_name}' expected number, got {type(val).__name__}"
    elif t in ("boolean", "bool"):
        if not isinstance(val, bool):
            return False, f"Property '{prop_name}' expected boolean, got {type(val).__name__}"
    elif t == "array":
        if not isinstance(val, list):
            return False, f"Property '{prop_name}' expected array/list, got {type(val).__name__}"
    elif t == "object":
        if not isinstance(val, dict):
            return False, f"Property '{prop_name}' expected object/dict, got {type(val).__name__}"
    return True, None


# ============================================================================
# 4. Gemini AI Compatibility Reasoner & Heuristic Fallback
# ============================================================================

class GeminiChangeAnalysis(BaseModel):
    change_id: str
    explanation: str
    impact: str
    suspected_rename: Optional[str] = None
    suggested_fix: str
    can_automate: bool
    missing_information: Optional[str] = None
    transformation_action: Optional[str] = None
    from_field: Optional[str] = None
    to_field: Optional[str] = None
    from_fields: Optional[List[str]] = None
    to_fields: Optional[List[str]] = None
    target_type: Optional[str] = None
    default_value: Optional[str] = None


class GeminiBatchOutput(BaseModel):
    analysis_items: List[GeminiChangeAnalysis]


def reason_with_gemini(
    changes: List[ChangeDetail],
    v1_schema_info: Dict[str, Any],
    v2_schema_info: Dict[str, Any],
) -> Tuple[Dict[str, GeminiChangeAnalysis], str]:
    """Uses Google Gemini to analyze breaking changes and generate structured fixes.

    If GEMINI_API_KEY is not set or API call fails, falls back to the deterministic
    heuristic reasoner so the application remains robust and testable offline.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        # Fallback to local heuristic reasoner
        return generate_heuristic_reasoning(changes, v1_schema_info, v2_schema_info), "deterministic_heuristic (No GEMINI_API_KEY provided)"

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL") or os.getenv("LLM_MODEL") or "gemini-3.8-flash"

        # Prepare prompt
        change_summaries = []
        for c in changes:
            change_summaries.append({
                "id": c.id,
                "type": c.change_type,
                "location": c.location,
                "description": c.description,
                "breaking_reason": c.breaking_reason,
                "v1_value": c.v1_value,
                "v2_value": c.v2_value,
            })

        prompt = f"""
You are an expert API compatibility engineer.
Analyze the following breaking and potentially breaking changes detected between OpenAPI v1 and OpenAPI v2:

DETECTED CHANGES:
{json.dumps(change_summaries, indent=2)}

V1 RELEVANT SCHEMA:
{json.dumps(v1_schema_info, indent=2)}

V2 RELEVANT SCHEMA:
{json.dumps(v2_schema_info, indent=2)}

CRITICAL INSTRUCTIONS:
1. Explain the technical root-cause and client impact of each change.
2. Identify likely rename relationships between removed and newly added fields (e.g., 'full_name' split into 'first_name' and 'last_name', or 'name' renamed to 'full_name'). Mark uncertain matches explicitly as 'suspected renames', not confirmed facts.
3. Suggest concrete fixes using simple transformations:
   - 'rename_field'
   - 'split_string'
   - 'combine_fields'
   - 'convert_type'
   - 'set_default' (ONLY for static parameters such as tenant_id or flags; NEVER invent personal user information like address, phone, or identity).
4. If personal information is missing or the change cannot be resolved automatically, set can_automate=false, explain why, and document missing_information.
5. Return a structured JSON response matching the requested schema.
"""

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=GeminiBatchOutput.model_json_schema(),
            ),
        )

        parsed_json = json.loads(response.text)
        batch = GeminiBatchOutput.model_validate(parsed_json)
        return {item.change_id: item for item in batch.analysis_items}, f"Google Gemini ({model_name})"

    except Exception as exc:
        # Graceful fallback on API error or network failure
        print(f"[APIBridge AI] Gemini reasoning error: {exc}. Falling back to deterministic reasoner.")
        fallback = generate_heuristic_reasoning(changes, v1_schema_info, v2_schema_info)
        return fallback, f"deterministic_heuristic (Fallback due to: {type(exc).__name__})"


def generate_heuristic_reasoning(
    changes: List[ChangeDetail],
    v1_schema_info: Dict[str, Any],
    v2_schema_info: Dict[str, Any],
) -> Dict[str, GeminiChangeAnalysis]:
    """Deterministic fallback reasoner to infer suspected renames, type conversions,

    and safe default transformations when Gemini is unavailable.
    """
    results: Dict[str, GeminiChangeAnalysis] = {}

    # Extract removed and added request fields to identify suspected renames/splits
    removed_req_fields = set()
    added_req_fields = set()
    for c in changes:
        if c.change_type == "REQUEST_BODY_FIELD_REMOVED" and isinstance(c.v1_value, str):
            removed_req_fields.add(c.v1_value)
        elif c.change_type in ("REQUEST_BODY_FIELD_REQUIRED_ADDED", "REQUEST_BODY_FIELD_OPTIONAL_ADDED") and isinstance(c.v2_value, str):
            added_req_fields.add(c.v2_value)

    for c in changes:
        cid = c.id
        ctype = c.change_type
        loc = c.location

        # Scenario: Field split / rename (e.g. full_name -> first_name + last_name)
        if ctype == "REQUEST_BODY_FIELD_REMOVED" and c.v1_value == "full_name" and {"first_name", "last_name"}.issubset(added_req_fields):
            results[cid] = GeminiChangeAnalysis(
                change_id=cid,
                explanation="Field 'full_name' was removed from the request schema.",
                impact="Legacy clients sending 'full_name' will have this field rejected or omitted.",
                suspected_rename="Suspected rename/split: 'full_name' appears split into 'first_name' and 'last_name'.",
                suggested_fix="Split 'full_name' into 'first_name' and 'last_name' using whitespace delimiter.",
                can_automate=True,
                transformation_action="split_string",
                from_field="full_name",
                to_fields=["first_name", "last_name"],
            )

        # Scenario: Required added field corresponding to the split (last_name)
        elif ctype == "REQUEST_BODY_FIELD_REQUIRED_ADDED" and c.v2_value == "last_name" and "full_name" in removed_req_fields:
            results[cid] = GeminiChangeAnalysis(
                change_id=cid,
                explanation="Field 'last_name' is newly required in v2 request body.",
                impact="Old clients omit 'last_name' and will be rejected with HTTP 400/422.",
                suspected_rename="Suspected dependency: derived from baseline 'full_name' attribute.",
                suggested_fix="Populated automatically when splitting 'full_name'.",
                can_automate=True,
                transformation_action="split_string",
                from_field="full_name",
                to_fields=["first_name", "last_name"],
            )

        # Scenario: Generic rename (e.g. name -> full_name)
        elif ctype == "REQUEST_BODY_FIELD_REMOVED" and c.v1_value in ("name", "user_name") and "full_name" in added_req_fields:
            results[cid] = GeminiChangeAnalysis(
                change_id=cid,
                explanation=f"Legacy property '{c.v1_value}' removed.",
                impact="Target service expects 'full_name'.",
                suspected_rename=f"Suspected rename: '{c.v1_value}' was renamed to 'full_name'.",
                suggested_fix=f"Rename '{c.v1_value}' to 'full_name'.",
                can_automate=True,
                transformation_action="rename_field",
                from_field=str(c.v1_value),
                to_field="full_name",
            )

        # Scenario: Type migration (e.g. id integer -> string, or age integer -> string)
        elif "TYPE_CHANGED" in ctype:
            target_t = str(c.v2_value) if c.v2_value else "string"
            field_name = loc.split(".")[-2] if "." in loc else "field"
            results[cid] = GeminiChangeAnalysis(
                change_id=cid,
                explanation=f"Field type changed from {c.v1_value} to {c.v2_value}.",
                impact=f"Clients serializing as {c.v1_value} will fail strict {c.v2_value} validation.",
                suspected_rename=None,
                suggested_fix=f"Convert field value from {c.v1_value} to {c.v2_value}.",
                can_automate=True,
                transformation_action="convert_type",
                from_field=field_name,
                target_type=target_t,
            )

        # Scenario: Required multi-tenancy / system parameter added (tenant_id)
        elif ctype in ("PARAM_REQUIRED_ADDED", "REQUEST_BODY_FIELD_REQUIRED_ADDED") and any(k in loc.lower() for k in ("tenant_id", "client_id", "version", "org_id")):
            param_name = "tenant_id" if "tenant_id" in loc else (c.v2_value if isinstance(c.v2_value, str) else "tenant_id")
            results[cid] = GeminiChangeAnalysis(
                change_id=cid,
                explanation=f"Required system parameter '{param_name}' was added.",
                impact="Old clients do not supply this value.",
                suspected_rename=None,
                suggested_fix=f"Inject default static identifier ('default') for backward compatibility.",
                can_automate=True,
                transformation_action="set_default",
                to_field=str(param_name),
                default_value="default",
            )

        # Scenario: Missing Personal / PII Information (e.g., required address or phone)
        elif ctype in ("PARAM_REQUIRED_ADDED", "REQUEST_BODY_FIELD_REQUIRED_ADDED") and any(pii in loc.lower() for pii in RESTRICTED_PII_KEYWORDS):
            param_name = c.v2_value if isinstance(c.v2_value, str) else "sensitive_field"
            results[cid] = GeminiChangeAnalysis(
                change_id=cid,
                explanation=f"Newly required personal information field '{param_name}' added in v2.",
                impact="Old clients do not possess or send this data.",
                suspected_rename=None,
                suggested_fix="Cannot safely auto-generate personal identity information.",
                can_automate=False,
                missing_information=f"Client application update required to collect user '{param_name}'.",
            )

        # Default fallback analysis
        else:
            is_break = c.category == ChangeCategory.BREAKING
            results[cid] = GeminiChangeAnalysis(
                change_id=cid,
                explanation=c.description,
                impact=c.breaking_reason or "No breaking client impact detected.",
                suspected_rename=None,
                suggested_fix="No automated transformation required." if not is_break else "Manual schema review recommended.",
                can_automate=False,
                missing_information="Change requires custom business handling." if is_break else None,
            )

    return results


# ============================================================================
# 5. Master Orchestrator: End-to-End Analysis & Fix Pipeline
# ============================================================================

def analyze_and_generate_fixes(
    diff_summary: DiffSummary,
    v1_spec_raw: str,
    v2_spec_raw: str,
    sample_request: Optional[Dict[str, Any]] = None,
    target_path: Optional[str] = None,
    target_method: Optional[str] = None,
) -> CompatibilityAnalysisResponse:
    """Orchestrates compatibility evaluation, AI reasoning, transformation generation,

    transformation execution, and payload schema validation.
    """
    items: List[CompatibilityItem] = []
    accumulated_transformations: List[TransformationInstruction] = []

    # Parse specs to extract target schemas for validation
    from diff_engine import OpenAPIDiffEngine
    engine = OpenAPIDiffEngine()
    doc1 = engine.resolve_references(engine.parse_and_validate(v1_spec_raw, "Spec v1"))
    doc2 = engine.resolve_references(engine.parse_and_validate(v2_spec_raw, "Spec v2"))

    # Extract target request body schema from v2 for validation
    target_p = target_path or "/users"
    target_m = (target_method or "post").lower()
    v2_target_schema = (
        doc2.get("paths", {})
        .get(target_p, {})
        .get(target_m, {})
        .get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    ) or {}

    v1_schema_info = doc1.get("components", {}).get("schemas", {})
    v2_schema_info = doc2.get("components", {}).get("schemas", {})

    # 1. Run Gemini / Heuristic Reasoner on all changes
    ai_analyses, ai_provider = reason_with_gemini(diff_summary.changes, v1_schema_info, v2_schema_info)

    # 2. Build Compatibility Items
    for change in diff_summary.changes:
        status, reason, can_auto, missing_info = evaluate_change_compatibility(change)
        loc = change.location.lower()
        is_req = "request" in loc or "parameters" in loc or change.change_type.startswith("PARAM_") or change.change_type.startswith("REQUEST_")
        is_resp = "response" in loc or change.change_type.startswith("RESPONSE_")

        ai_item = ai_analyses.get(change.id)
        gemini_exp = ai_item.explanation if ai_item else None
        gemini_impact = ai_item.impact if ai_item else change.breaking_reason
        suspected_rename = ai_item.suspected_rename if ai_item else None
        suggested_fix = ai_item.suggested_fix if ai_item else None

        transformations_for_change: List[TransformationInstruction] = []
        fix_status = FixStatus.NONE

        if ai_item and ai_item.transformation_action:
            act_type = TransformationActionType(ai_item.transformation_action)
            instr = TransformationInstruction(
                action=act_type,
                from_field=ai_item.from_field,
                to_field=ai_item.to_field,
                from_fields=ai_item.from_fields,
                to_fields=ai_item.to_fields,
                target_type=ai_item.target_type,
                default_value=ai_item.default_value,
                description=ai_item.suggested_fix,
                is_safe=ai_item.can_automate,
            )
            transformations_for_change.append(instr)
            accumulated_transformations.append(instr)
            fix_status = FixStatus.FIX_GENERATED if ai_item.can_automate else FixStatus.MANUAL_INTERVENTION_REQUIRED
        elif status == CompatibilityStatus.POTENTIALLY_BREAKING and not can_auto:
            fix_status = FixStatus.MANUAL_INTERVENTION_REQUIRED

        items.append(
            CompatibilityItem(
                change_id=change.id,
                change_type=change.change_type,
                location=change.location,
                path=change.path,
                method=change.method,
                is_request=is_req,
                is_response=is_resp,
                compatibility_status=status,
                compatibility_reason=reason,
                can_automate_fix=can_auto and (ai_item.can_automate if ai_item else True),
                missing_information=missing_info or (ai_item.missing_information if ai_item else None),
                gemini_explanation=gemini_exp,
                gemini_impact=gemini_impact,
                suspected_rename=suspected_rename,
                suggested_fix=suggested_fix,
                suggested_transformations=transformations_for_change,
                fix_status=fix_status,
            )
        )

    # 3. Apply Transformations to Sample Request Payload (if provided or default sample)
    effective_sample = sample_request
    if effective_sample is None and "CreateUserRequest" in str(v1_spec_raw):
        # Default baseline sample for User service demo
        effective_sample = {
            "full_name": "Jane Doe",
            "email": "jane.doe@example.com",
            "age": 28,
        }

    transformed_payload = None
    validation_report = None

    if effective_sample is not None and accumulated_transformations:
        transformed_payload, _ = apply_transformations(effective_sample, accumulated_transformations)
        if v2_target_schema:
            validation_report = validate_payload_against_schema(transformed_payload, v2_target_schema)

            # Update item statuses to FIX_VALIDATED if validation passed
            if validation_report.is_valid:
                for itm in items:
                    if itm.fix_status == FixStatus.FIX_GENERATED:
                        itm.fix_status = FixStatus.FIX_VALIDATED

    # 4. Compute Counts & Summary
    comp_cnt = sum(1 for i in items if i.compatibility_status == CompatibilityStatus.COMPATIBLE)
    pot_cnt = sum(1 for i in items if i.compatibility_status == CompatibilityStatus.POTENTIALLY_BREAKING)
    incomp_cnt = sum(1 for i in items if i.compatibility_status == CompatibilityStatus.INCOMPATIBLE)
    inconc_cnt = sum(1 for i in items if i.compatibility_status == CompatibilityStatus.INCONCLUSIVE)

    fix_gen_cnt = sum(1 for i in items if i.fix_status == FixStatus.FIX_GENERATED)
    fix_val_cnt = sum(1 for i in items if i.fix_status == FixStatus.FIX_VALIDATED)
    manual_cnt = sum(1 for i in items if i.fix_status == FixStatus.MANUAL_INTERVENTION_REQUIRED)

    overall_status = CompatibilityStatus.COMPATIBLE
    if incomp_cnt > 0:
        overall_status = CompatibilityStatus.INCOMPATIBLE
    elif pot_cnt > 0:
        overall_status = CompatibilityStatus.POTENTIALLY_BREAKING
    elif inconc_cnt > 0:
        overall_status = CompatibilityStatus.INCONCLUSIVE

    summary_msg = (
        f"Compatibility Analysis: {comp_cnt} compatible, {pot_cnt} potentially breaking, "
        f"{incomp_cnt} incompatible changes. {fix_gen_cnt + fix_val_cnt} fix(es) generated."
    )

    return CompatibilityAnalysisResponse(
        total_changes=len(items),
        compatible_count=comp_cnt,
        potentially_breaking_count=pot_cnt,
        incompatible_count=incomp_cnt,
        inconclusive_count=inconc_cnt,
        fixes_generated_count=fix_gen_cnt,
        fixes_validated_count=fix_val_cnt,
        manual_intervention_count=manual_cnt,
        overall_compatibility=overall_status,
        summary_message=summary_msg,
        items=items,
        sample_request_original=effective_sample,
        sample_request_transformed=transformed_payload,
        payload_validation=validation_report,
        ai_provider=ai_provider,
    )

