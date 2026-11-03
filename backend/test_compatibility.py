"""Automated Tests for APIBridge AI Compatibility Analyzer, Gemini Reasoner,
Transformation Engine, and Fix Validation.

Covers all 10 required test scenarios.
"""

import pytest
from diff_engine import ChangeCategory, ChangeDetail, DiffSummary, OpenAPIDiffEngine
from compatibility import (
    CompatibilityStatus,
    FixStatus,
    TransformationActionType,
    TransformationInstruction,
    analyze_and_generate_fixes,
    apply_transformations,
    convert_primitive_type,
    evaluate_change_compatibility,
    generate_heuristic_reasoning,
    validate_payload_against_schema,
)


@pytest.fixture
def engine():
    return OpenAPIDiffEngine()


# ----------------------------------------------------------------------------
# Scenario 1: Adding an optional request field
# ----------------------------------------------------------------------------
def test_scenario_1_adding_optional_request_field_is_compatible():
    change = ChangeDetail(
        id="CHG-0001",
        category=ChangeCategory.NON_BREAKING,
        change_type="PARAM_OPTIONAL_ADDED",
        location="GET /users.parameters.query.filter",
        description="New optional parameter 'filter' added in v2.",
    )
    status, reason, can_auto, missing_info = evaluate_change_compatibility(change)
    assert status == CompatibilityStatus.COMPATIBLE
    assert "optional" in reason.lower()
    assert can_auto is False
    assert missing_info is None


# ----------------------------------------------------------------------------
# Scenario 2: Adding a required request field
# ----------------------------------------------------------------------------
def test_scenario_2_adding_required_request_field_is_potentially_breaking():
    change = ChangeDetail(
        id="CHG-0002",
        category=ChangeCategory.BREAKING,
        change_type="PARAM_REQUIRED_ADDED",
        location="GET /users.parameters.query.tenant_id",
        description="New required parameter 'tenant_id' added in v2.",
        breaking_reason="Existing clients do not send 'tenant_id'.",
        v2_value="tenant_id",
    )
    status, reason, can_auto, missing_info = evaluate_change_compatibility(change)
    assert status == CompatibilityStatus.POTENTIALLY_BREAKING
    assert "required" in reason.lower()
    assert can_auto is True


# ----------------------------------------------------------------------------
# Scenario 3: Removing an existing request field
# ----------------------------------------------------------------------------
def test_scenario_3_removing_existing_request_field():
    change = ChangeDetail(
        id="CHG-0003",
        category=ChangeCategory.BREAKING,
        change_type="REQUEST_BODY_FIELD_REMOVED",
        location="POST /users.requestBody.schema.properties.deprecated_flag",
        description="Field 'deprecated_flag' was removed in v2.",
        v1_value="deprecated_flag",
    )
    status, reason, can_auto, _ = evaluate_change_compatibility(change)
    assert status == CompatibilityStatus.POTENTIALLY_BREAKING
    assert "removed" in reason.lower()


# ----------------------------------------------------------------------------
# Scenario 4: Removing an existing response field
# ----------------------------------------------------------------------------
def test_scenario_4_removing_existing_response_field():
    change = ChangeDetail(
        id="CHG-0004",
        category=ChangeCategory.BREAKING,
        change_type="RESPONSE_FIELD_REMOVED",
        location="GET /users.responses['200'].schema.properties.avatar_url",
        description="Response field 'avatar_url' was removed in v2.",
        breaking_reason="Existing clients consuming 'avatar_url' encounter errors.",
        v1_value="avatar_url",
    )
    status, reason, can_auto, missing_info = evaluate_change_compatibility(change)
    assert status == CompatibilityStatus.POTENTIALLY_BREAKING
    assert can_auto is False
    assert "no longer computes" in (missing_info or "").lower()


# ----------------------------------------------------------------------------
# Scenario 5: Changing a field's data type
# ----------------------------------------------------------------------------
def test_scenario_5_changing_field_data_type():
    change = ChangeDetail(
        id="CHG-0005",
        category=ChangeCategory.BREAKING,
        change_type="REQUEST_BODY_FIELD_TYPE_CHANGED",
        location="POST /users.requestBody.schema.properties.age.type",
        description="Field 'age' changed type from 'integer' to 'string'.",
        v1_value="integer",
        v2_value="string",
    )
    status, reason, can_auto, missing_info = evaluate_change_compatibility(change)
    assert status == CompatibilityStatus.POTENTIALLY_BREAKING
    assert "migrated" in reason.lower()
    assert can_auto is True

    # Test type conversion execution
    assert convert_primitive_type(28, "string") == "28"
    assert convert_primitive_type("42", "integer") == 42
    assert convert_primitive_type("true", "boolean") is True


# ----------------------------------------------------------------------------
# Scenario 6: Renaming an existing field
# ----------------------------------------------------------------------------
def test_scenario_6_renaming_field_suspected_rename():
    c_removed = ChangeDetail(
        id="CHG-0006",
        category=ChangeCategory.BREAKING,
        change_type="REQUEST_BODY_FIELD_REMOVED",
        location="POST /users.requestBody.schema.properties.name",
        description="Field 'name' removed.",
        v1_value="name",
    )
    c_added = ChangeDetail(
        id="CHG-0007",
        category=ChangeCategory.BREAKING,
        change_type="REQUEST_BODY_FIELD_REQUIRED_ADDED",
        location="POST /users.requestBody.schema.properties.full_name",
        description="Field 'full_name' added.",
        v2_value="full_name",
    )

    reasoning = generate_heuristic_reasoning([c_removed, c_added], {}, {})
    assert "CHG-0006" in reasoning
    item = reasoning["CHG-0006"]
    assert item.suspected_rename is not None
    assert "renamed to 'full_name'" in item.suspected_rename
    assert item.transformation_action == "rename_field"
    assert item.from_field == "name"
    assert item.to_field == "full_name"


# ----------------------------------------------------------------------------
# Scenario 7: Applying a simple field mapping
# ----------------------------------------------------------------------------
def test_scenario_7_applying_simple_field_mapping():
    payload = {"user_handle": "alice99", "email": "alice@example.com"}
    instructions = [
        TransformationInstruction(
            action=TransformationActionType.RENAME_FIELD,
            from_field="user_handle",
            to_field="username",
            description="Rename 'user_handle' to 'username'",
        )
    ]
    transformed, logs = apply_transformations(payload, instructions)
    assert "user_handle" not in transformed
    assert transformed["username"] == "alice99"
    assert transformed["email"] == "alice@example.com"
    assert len(logs) == 1
    assert "Renamed" in logs[0]


# ----------------------------------------------------------------------------
# Scenario 8: Applying a default value
# ----------------------------------------------------------------------------
def test_scenario_8_applying_default_value():
    payload = {"username": "bob"}
    instructions = [
        TransformationInstruction(
            action=TransformationActionType.SET_DEFAULT,
            to_field="tenant_id",
            default_value="org-default",
            description="Set default tenant_id to 'org-default'",
        )
    ]
    transformed, logs = apply_transformations(payload, instructions)
    assert transformed["tenant_id"] == "org-default"
    assert transformed["username"] == "bob"
    assert "Set default" in logs[0]


# ----------------------------------------------------------------------------
# Scenario 9: Validating a transformed payload against v2
# ----------------------------------------------------------------------------
def test_scenario_9_validating_transformed_payload_against_v2():
    v2_schema = {
        "type": "object",
        "required": ["first_name", "last_name", "email", "age"],
        "properties": {
            "first_name": {"type": "string"},
            "last_name": {"type": "string"},
            "email": {"type": "string"},
            "age": {"type": "integer"},
        },
    }

    # Transformed payload with split names
    valid_payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@example.com",
        "age": 28,
    }
    result_valid = validate_payload_against_schema(valid_payload, v2_schema)
    assert result_valid.is_valid is True
    assert len(result_valid.validation_errors) == 0

    # Invalid payload missing required property 'last_name' and wrong type for 'age'
    invalid_payload = {
        "first_name": "Jane",
        "email": "jane@example.com",
        "age": "twenty-eight",
    }
    result_invalid = validate_payload_against_schema(invalid_payload, v2_schema)
    assert result_invalid.is_valid is False
    assert any("Missing required property 'last_name'" in err for err in result_invalid.validation_errors)
    assert any("Property 'age' expected integer" in err for err in result_invalid.validation_errors)


# ----------------------------------------------------------------------------
# Scenario 10: Handling missing or ambiguous mapping information
# ----------------------------------------------------------------------------
def test_scenario_10_missing_or_ambiguous_information_requires_manual_intervention():
    # Attempting to auto-invent PII (address) must be blocked
    payload = {"name": "Charlie"}
    instructions = [
        TransformationInstruction(
            action=TransformationActionType.SET_DEFAULT,
            to_field="user_residential_address",
            default_value="123 Main St",
            description="Auto-invent address",
        )
    ]
    transformed, logs = apply_transformations(payload, instructions)
    assert "user_residential_address" not in transformed
    assert any("cannot be automatically generated" in log for log in logs)

    # Change requiring user address must produce MANUAL_INTERVENTION_REQUIRED
    change_address = ChangeDetail(
        id="CHG-0010",
        category=ChangeCategory.BREAKING,
        change_type="REQUEST_BODY_FIELD_REQUIRED_ADDED",
        location="POST /users.requestBody.schema.properties.address",
        description="Newly required request field 'address' added in v2.",
        v2_value="address",
    )
    reasoning = generate_heuristic_reasoning([change_address], {}, {})
    item = reasoning["CHG-0010"]
    assert item.can_automate is False
    assert item.missing_information is not None
    assert "update required" in item.missing_information.lower()


# ----------------------------------------------------------------------------
# Integration Test: End-to-End Analyze & Generate Fixes with Sample Specs
# ----------------------------------------------------------------------------
def test_end_to_end_analyze_and_generate_fixes(engine):
    v1 = """
    openapi: 3.0.0
    info:
      title: User Service
      version: 1.0.0
    paths:
      /users:
        post:
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  type: object
                  required:
                    - full_name
                    - email
                  properties:
                    full_name:
                      type: string
                    email:
                      type: string
          responses:
            '201':
              description: Created
    """

    v2 = """
    openapi: 3.0.0
    info:
      title: User Service
      version: 2.0.0
    paths:
      /users:
        post:
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  type: object
                  required:
                    - first_name
                    - last_name
                    - email
                  properties:
                    first_name:
                      type: string
                    last_name:
                      type: string
                    email:
                      type: string
          responses:
            '201':
              description: Created
    """

    diff = engine.compare(v1, v2)
    sample_req = {"full_name": "Alice Smith", "email": "alice@example.com"}

    response = analyze_and_generate_fixes(
        diff_summary=diff,
        v1_spec_raw=v1,
        v2_spec_raw=v2,
        sample_request=sample_req,
        target_path="/users",
        target_method="post",
    )

    assert response.total_changes > 0
    assert response.potentially_breaking_count > 0
    assert response.sample_request_transformed is not None
    # Check that 'full_name' was split into first_name and last_name
    assert response.sample_request_transformed.get("first_name") == "Alice"
    assert response.sample_request_transformed.get("last_name") == "Smith"
    assert response.sample_request_transformed.get("email") == "alice@example.com"
    assert "full_name" not in response.sample_request_transformed

    # Payload validation should pass against v2 schema
    assert response.payload_validation is not None
    assert response.payload_validation.is_valid is True

