"""Automated Tests for OpenAPI Structural Diff Engine
"""

from pathlib import Path
import pytest
from diff_engine import ChangeCategory, DiffSummary, OpenAPIDiffEngine


@pytest.fixture
def engine():
    return OpenAPIDiffEngine()


def test_identical_specifications_is_compatible(engine):
    spec = """
    openapi: 3.0.0
    info:
      title: Test API
      version: 1.0.0
    paths:
      /items:
        get:
          responses:
            '200':
              description: OK
    """
    diff: DiffSummary = engine.compare(spec, spec)
    assert diff.total_changes == 0
    assert diff.breaking_count == 0
    assert diff.non_breaking_count == 0
    assert diff.is_compatible is True


def test_removed_path_is_breaking(engine):
    v1 = """
    openapi: 3.0.0
    info:
      title: API
      version: 1.0.0
    paths:
      /users:
        get:
          responses:
            '200':
              description: OK
      /legacy:
        get:
          responses:
            '200':
              description: OK
    """
    v2 = """
    openapi: 3.0.0
    info:
      title: API
      version: 2.0.0
    paths:
      /users:
        get:
          responses:
            '200':
              description: OK
    """
    diff = engine.compare(v1, v2)
    assert diff.is_compatible is False
    assert diff.breaking_count == 1
    breaking_change = diff.changes[0]
    assert breaking_change.change_type == "PATH_REMOVED"
    assert breaking_change.path == "/legacy"
    assert breaking_change.category == ChangeCategory.BREAKING


def test_added_path_is_non_breaking(engine):
    v1 = """
    openapi: 3.0.0
    info:
      title: API
      version: 1.0.0
    paths:
      /users:
        get:
          responses:
            '200':
              description: OK
    """
    v2 = """
    openapi: 3.0.0
    info:
      title: API
      version: 2.0.0
    paths:
      /users:
        get:
          responses:
            '200':
              description: OK
      /users/new-feature:
        get:
          responses:
            '200':
              description: OK
    """
    diff = engine.compare(v1, v2)
    assert diff.is_compatible is True
    assert diff.breaking_count == 0
    assert diff.non_breaking_count == 1
    assert diff.changes[0].change_type == "PATH_ADDED"
    assert diff.changes[0].category == ChangeCategory.NON_BREAKING


def test_removed_method_is_breaking(engine):
    v1 = """
    openapi: 3.0.0
    info:
      title: API
      version: 1.0.0
    paths:
      /users:
        get:
          responses:
            '200':
              description: OK
        delete:
          responses:
            '204':
              description: Deleted
    """
    v2 = """
    openapi: 3.0.0
    info:
      title: API
      version: 2.0.0
    paths:
      /users:
        get:
          responses:
            '200':
              description: OK
    """
    diff = engine.compare(v1, v2)
    assert diff.breaking_count == 1
    assert diff.changes[0].change_type == "METHOD_REMOVED"
    assert diff.changes[0].method == "DELETE"


def test_new_required_parameter_is_breaking_but_optional_is_not(engine):
    v1 = """
    openapi: 3.0.0
    info:
      title: API
      version: 1.0.0
    paths:
      /users:
        get:
          parameters:
            - name: existing
              in: query
              required: false
              schema:
                type: string
          responses:
            '200':
              description: OK
    """
    v2 = """
    openapi: 3.0.0
    info:
      title: API
      version: 2.0.0
    paths:
      /users:
        get:
          parameters:
            - name: existing
              in: query
              required: false
              schema:
                type: string
            - name: mandatory_token
              in: query
              required: true
              schema:
                type: string
            - name: optional_tag
              in: query
              required: false
              schema:
                type: string
          responses:
            '200':
              description: OK
    """
    diff = engine.compare(v1, v2)
    assert diff.breaking_count == 1
    assert diff.non_breaking_count == 1
    breaking = [c for c in diff.changes if c.category == ChangeCategory.BREAKING][0]
    non_breaking = [c for c in diff.changes if c.category == ChangeCategory.NON_BREAKING][0]
    assert breaking.change_type == "PARAM_REQUIRED_ADDED"
    assert "mandatory_token" in breaking.location
    assert non_breaking.change_type == "PARAM_OPTIONAL_ADDED"
    assert "optional_tag" in non_breaking.location


def test_request_body_field_removed_and_newly_required(engine):
    v1 = """
    openapi: 3.0.0
    info:
      title: API
      version: 1.0.0
    paths:
      /submit:
        post:
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  type: object
                  properties:
                    deprecated_field:
                      type: string
                    preserved_field:
                      type: string
          responses:
            '200':
              description: OK
    """
    v2 = """
    openapi: 3.0.0
    info:
      title: API
      version: 2.0.0
    paths:
      /submit:
        post:
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  type: object
                  required:
                    - newly_required_field
                  properties:
                    preserved_field:
                      type: string
                    newly_required_field:
                      type: string
                    optional_field:
                      type: string
          responses:
            '200':
              description: OK
    """
    diff = engine.compare(v1, v2)
    change_types = [c.change_type for c in diff.changes]
    assert "REQUEST_BODY_FIELD_REMOVED" in change_types
    assert "REQUEST_BODY_FIELD_REQUIRED_ADDED" in change_types
    assert "REQUEST_BODY_FIELD_OPTIONAL_ADDED" in change_types


def test_response_field_removed_and_type_changed(engine):
    v1 = """
    openapi: 3.0.0
    info:
      title: API
      version: 1.0.0
    paths:
      /data:
        get:
          responses:
            '200':
              content:
                application/json:
                  schema:
                    type: object
                    properties:
                      removed_metric:
                        type: integer
                      count:
                        type: integer
    """
    v2 = """
    openapi: 3.0.0
    info:
      title: API
      version: 2.0.0
    paths:
      /data:
        get:
          responses:
            '200':
              content:
                application/json:
                  schema:
                    type: object
                    properties:
                      count:
                        type: string
                      added_metric:
                        type: boolean
    """
    diff = engine.compare(v1, v2)
    change_types = {c.change_type: c for c in diff.changes}
    assert "RESPONSE_FIELD_REMOVED" in change_types
    assert change_types["RESPONSE_FIELD_REMOVED"].category == ChangeCategory.BREAKING
    assert "RESPONSE_200_FIELD_TYPE_CHANGED" in change_types
    assert change_types["RESPONSE_200_FIELD_TYPE_CHANGED"].category == ChangeCategory.BREAKING
    assert "RESPONSE_FIELD_ADDED" in change_types
    assert change_types["RESPONSE_FIELD_ADDED"].category == ChangeCategory.NON_BREAKING


def test_internal_ref_resolution(engine):
    v1 = """
    openapi: 3.0.0
    info:
      title: API
      version: 1.0.0
    paths:
      /account:
        get:
          responses:
            '200':
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/Account'
    components:
      schemas:
        Account:
          type: object
          properties:
            balance:
              type: integer
    """
    v2 = """
    openapi: 3.0.0
    info:
      title: API
      version: 2.0.0
    paths:
      /account:
        get:
          responses:
            '200':
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/Account'
    components:
      schemas:
        Account:
          type: object
          properties:
            balance:
              type: number
            currency:
              type: string
    """
    diff = engine.compare(v1, v2)
    change_types = [c.change_type for c in diff.changes]
    assert "RESPONSE_200_FIELD_TYPE_CHANGED" in change_types
    assert "RESPONSE_FIELD_ADDED" in change_types


def test_circular_ref_handling_does_not_infinite_loop(engine):
    spec = """
    openapi: 3.0.0
    info:
      title: Circular API
      version: 1.0.0
    paths:
      /node:
        get:
          responses:
            '200':
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/Node'
    components:
      schemas:
        Node:
          type: object
          properties:
            parent:
              $ref: '#/components/schemas/Node'
    """
    # Resolving references on circular schema should not raise recursion error
    resolved = engine.resolve_references(engine.parse_and_validate(spec))
    assert resolved is not None


def test_malformed_input_raises_value_error(engine):
    with pytest.raises(ValueError, match="could not be parsed as valid JSON or YAML"):
        engine.compare("foo: [unclosed bracket", "openapi: 3.0.0\npaths: {}")

    with pytest.raises(ValueError, match="root must be a valid JSON/YAML object/dictionary"):
        engine.compare("just_a_scalar_string", "openapi: 3.0.0\npaths: {}")

    with pytest.raises(ValueError, match="is empty"):
        engine.compare("", "openapi: 3.0.0\npaths: {}")

    with pytest.raises(ValueError, match="missing required OpenAPI structure"):
        engine.compare("random_key: 123", "openapi: 3.0.0\npaths: {}")


def test_sample_files_comparison(engine):
    samples_dir = Path(__file__).parent / "samples"
    v1_file = samples_dir / "v1_user_service.yaml"
    v2_file = samples_dir / "v2_user_service.yaml"

    assert v1_file.exists()
    assert v2_file.exists()

    diff = engine.compare(v1_file.read_text(encoding="utf-8"), v2_file.read_text(encoding="utf-8"))
    assert diff.is_compatible is False
    assert diff.breaking_count > 0
    assert diff.non_breaking_count > 0
    assert diff.total_changes == diff.breaking_count + diff.non_breaking_count
