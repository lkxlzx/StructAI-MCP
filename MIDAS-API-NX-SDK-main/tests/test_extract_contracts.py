"""Guards for the manual-to-contract extractor.

These run against synthetic chapter text rather than the sibling manual repo, so
the suite still passes with no live server and no second checkout. The one thing
they will not let slide is the extractor inventing certainty: a draft that fills
in `safeToOmit` from a manual that says "Optional" would turn the documentation
into evidence, and the CI gate built on the difference between those two would
stop meaning anything.
"""

import dataclasses
import json
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import extract_contracts as ex  # noqa: E402

CHAPTER = """# 99 DB — Synthetic

## 1. `/db/SYNTH` — Synthetic Endpoint

- **Methods**: `POST`, `GET`, `PUT`, `DELETE`
- **Source**: [Synth ↗](https://support.midasuser.com/hc/en-us/articles/1)

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Ordering Index | `"NO"` | Integer | - | Read Only |
| 2 | Name | `"NAME"` | String | - | Required |
| 3 | Flag | `"bFLAG"` | Boolean | false | Optional |
| 4 | Count | `"COUNT"` | Number | 0 | Optional |
| 5 | Span check | `"SPAN"` | Number | - | Required (bEXACTSPAN=true) |
| 6 | Items | `"ITEMS"` | Array [Object] | - | Required |
| 7 | └ Item name | `"ITEMS[].ITEM_NAME"` | String | - | Required |
| 8 | └ Item value | `"ITEMS[].ITEM_VALUE"` | Number | 1 | Optional |
| 9 | Nested leaf | `"CFG.MODE"` | String | - | Optional |
| 10 | Ambiguous | `"A" / "B"` | String | - | Optional |
| 11 | Non-negative value | `"NON_NEGATIVE"` | Number (≥0) | - | Required |
| 12 | Fixed code | `"CODE"` | String(7) | - | Required |
| 13 | Fixed vector | `"VECTOR"` | Number,3 | - | Required |
| 14 | Inline boolean default | `"INLINE_DEFAULT"` | Boolean (default false) | - | Optional |
| 15 | Fixed numeric value | `"CONST_VALUE"` | Number (const 0.75) | - | Read Only |
| 16 | Reversed numeric choices (Zero: 0 / One: 1) | `"REVERSED"` | Integer (enum) | - | Required |
| 17 | Explicit paired fields | `"ENABLED"` / `"LIMIT"` | Boolean / Number | false / 0 | Optional / Required |
| 18 | Digit-prefixed wire key | `"7TH_DOF_TYPE"` | Integer | 0 | Optional |
| 19 | Escaped fixed vector | `"ESCAPED_VECTOR"` | Array \\[Number, 3\\] | - | Required |
| 20 | Conditional from description (`MODE="SPECIAL"`) | `"SPECIAL_VALUE"` | Number | - | Conditional Required |
| 21 | Empty item defaults | `"DEFAULT_ITEMS"` | Array [Number] | [] | Optional |
| 22 | Empty object default | `"DEFAULT_OPTIONS"` | Object | {} | Optional |
| 23 | Quoted string default | `"DEFAULT_MODE"` | String | `"FIRST"` | Optional |
| 24 | Variant discriminator | `"TYPE"` | String | - | Required |

### Variant table

#### TYPE=SPECIAL 전용

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Special only | `"SPECIAL"` | String | - | Required |
"""


@pytest.fixture
def section(tmp_path: Path) -> ex.Section:
    path = tmp_path / "99_DB_Synthetic.md"
    path.write_text(CHAPTER, encoding="utf-8")
    sections = ex.parse_chapter(path)
    assert len(sections) == 1
    return sections[0]


def test_section_metadata(section: ex.Section):
    assert section.endpoint == "/db/SYNTH"
    assert section.id == "db-synth"
    assert section.title == "Synthetic Endpoint"
    assert section.methods == ["DELETE", "GET", "POST", "PUT"]
    assert section.source_url == "https://support.midasuser.com/hc/en-us/articles/1"


@pytest.mark.parametrize(
    ("heading", "intro", "expected_title"),
    [
        pytest.param(
            "## 1. `/db/TITLE`",
            "> **Title in Blockquote** - endpoint description",
            "Title in Blockquote",
            id="opening-blockquote-title",
        ),
        pytest.param(
            "## 1. `/db/TITLE` - Title in Heading",
            "> **Ignored Blockquote Title** - endpoint description",
            "Title in Heading",
            id="heading-title-wins",
        ),
    ],
)
def test_section_title_reads_the_documented_intro_form(
    tmp_path: Path, heading: str, intro: str, expected_title: str
):
    path = tmp_path / "99_DB_Title.md"
    path.write_text(f"# Synthetic\n\n{heading}\n\n{intro}\n\n### Specifications\n", encoding="utf-8")

    assert ex.parse_chapter(path)[0].title == expected_title


@pytest.mark.parametrize(
    ("label_header", "expected_title"),
    [
        pytest.param("기능", "Korean Function Label", id="korean-function-column"),
        pytest.param("설명", "Korean Description Label", id="korean-description-column"),
        pytest.param("Feature", "English Feature Label", id="english-feature-column"),
    ],
)
def test_section_title_reads_the_documented_contents_table_label(
    tmp_path: Path, label_header: str, expected_title: str
):
    path = tmp_path / "99_DB_Title.md"
    path.write_text(
        "# Synthetic\n\n"
        f"| No. | Endpoint | {label_header} | Methods |\n"
        "|---|---|---|---|\n"
        f"| 1 | [`/db/TITLE`](#1-dbtitle) | {expected_title} | GET |\n\n"
        "## 1. `/db/TITLE`\n",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    assert section.title == expected_title
    assert section.methods == ["GET"]


@pytest.mark.parametrize(
    ("heading", "intro", "expected_title"),
    [
        pytest.param(
            "## 1. `/db/TITLE` - Heading Title",
            "> **Blockquote Title** - endpoint description",
            "Heading Title",
            id="heading-before-blockquote-and-contents-table",
        ),
        pytest.param(
            "## 1. `/db/TITLE`",
            "> **Blockquote Title** - endpoint description",
            "Blockquote Title",
            id="blockquote-before-contents-table",
        ),
    ],
)
def test_section_title_uses_contents_table_only_after_heading_and_blockquote(
    tmp_path: Path, heading: str, intro: str, expected_title: str
):
    path = tmp_path / "99_DB_Title.md"
    path.write_text(
        "# Synthetic\n\n"
        "| No. | Endpoint | 기능 |\n"
        "|---|---|---|\n"
        "| 1 | [`/db/TITLE`](#1-dbtitle) | Contents Table Title |\n\n"
        f"{heading}\n\n"
        f"{intro}\n",
        encoding="utf-8",
    )

    assert ex.parse_chapter(path)[0].title == expected_title


def test_requiredness_and_defaults_come_from_the_table(section: ex.Section):
    fields = {f.key: f for f in section.tables[0].fields}

    assert fields["NO"].requirement == "read_only"
    assert fields["NAME"].requirement == "required"
    assert fields["NAME"].documented_default is None
    assert fields["bFLAG"].requirement == "optional"
    assert fields["bFLAG"].documented_default is False
    assert fields["COUNT"].documented_default == 0


def test_render_draft_keeps_manual_condition_and_structured_applies_when(section: ex.Section):
    field = next(field for field in section.tables[0].fields if field.key == "SPECIAL_VALUE")
    field.condition = "MODE=\"SPECIAL\""
    field.applies_when = [
        ("MODE", ("SPECIAL",)),
        ("OPTIONS.ENABLED", (True,)),
        # Several documented values for one path render as `in`, not as a
        # repeated `equals` and not as a guess at the rest of the enum.
        ("STAGE", (1, 2)),
    ]

    rendered = yaml.safe_load(ex.render_draft(section))["fields"]
    rendered_field = next(entry for entry in rendered if entry["key"] == "SPECIAL_VALUE")
    assert rendered_field["condition"] == 'MODE="SPECIAL"'
    assert rendered_field["appliesWhen"] == [
        {"path": "MODE", "equals": "SPECIAL"},
        {"path": "OPTIONS.ENABLED", "equals": True},
        {"path": "STAGE", "in": [1, 2]},
    ]


def test_inline_conditions_are_kept_verbatim(section: ex.Section):
    span = {f.key: f for f in section.tables[0].fields}["SPAN"]

    assert span.requirement == "conditional"
    assert span.condition == "bEXACTSPAN=true"


def test_exact_description_condition_completes_a_conditional_required_marker(section: ex.Section):
    special = {field.key: field for field in section.tables[0].fields}["SPECIAL_VALUE"]

    assert special.requirement == "conditional"
    assert special.condition == 'MODE="SPECIAL"'
    assert not special.notes


@pytest.mark.parametrize(
    ("description_form", "expected_condition"),
    [
        pytest.param(
            'Detail (MODE\uac00 USER\uc77c \ub54c \ud544\uc218)',
            'MODE\uac00 USER\uc77c \ub54c \ud544\uc218',
            id="parenthesized_korean_selector",
        ),
        pytest.param(
            "Detail \u2014 OPT_USE\uac00 true\uc77c \ub54c \ud544\uc218",
            "OPT_USE\uac00 true\uc77c \ub54c \ud544\uc218",
            id="em_dash_korean_selector",
        ),
        pytest.param(
            "Detail (when INPUT_MODE is MANUAL)",
            "when INPUT_MODE is MANUAL",
            id="parenthesized_english_selector",
        ),
    ],
)
def test_explicit_description_condition_forms_are_retained_verbatim(
    description_form: str, expected_condition: str, tmp_path: Path
):
    path = tmp_path / "99_DB_DescriptionCondition.md"
    path.write_text(
        "## 1. `/db/DESCRIPTION-CONDITION` -- Description condition\n\n"
        "| No. | Description | Key | Value Type | Default | Required |\n"
        "|-----|-------------|-----|------------|---------|----------|\n"
        f"| 1 | {description_form} | `DETAIL` | Number | - | Conditional Required |\n",
        encoding="utf-8",
    )

    detail = ex.parse_chapter(path)[0].tables[0].fields[0]
    assert detail.requirement == "conditional"
    assert detail.condition == expected_condition
    assert not detail.notes


def test_dotted_paths_become_nested_fields(section: ex.Section):
    fields = {f.key: f for f in section.tables[0].fields}

    items = fields["ITEMS"]
    assert items.type == "array"
    assert items.items == {"type": "object"}
    assert [child.key for child in items.properties] == ["ITEM_NAME", "ITEM_VALUE"]
    assert items.properties[1].documented_default == 1

    # A parent the manual never gave a row of its own is synthesized, and says so.
    cfg = fields["CFG"]
    assert cfg.type == "object"
    assert [child.key for child in cfg.properties] == ["MODE"]
    assert any("no row of its own" in note for note in cfg.notes)


def test_ambiguous_keys_are_flagged_not_guessed(section: ex.Section):
    ambiguous = {f.key: f for f in section.tables[0].fields}

    assert 'A" / "B' in ambiguous
    assert any("more than one" in note for note in ambiguous['A" / "B'].notes)


def test_exact_digit_prefixed_wire_key_is_not_treated_as_an_ambiguous_label(section: ex.Section):
    fields = {field.key: field for field in section.tables[0].fields}

    assert fields["7TH_DOF_TYPE"].type == "integer"
    assert not fields["7TH_DOF_TYPE"].notes


def test_explicit_type_constraints_are_preserved(section: ex.Section):
    fields = {field.key: field for field in section.tables[0].fields}
    assert fields["NON_NEGATIVE"].type == "number"
    assert fields["NON_NEGATIVE"].constraints == {"minimum": 0}
    assert fields["CODE"].type == "string"
    assert fields["CODE"].constraints == {"minLength": 7, "maxLength": 7}
    assert fields["VECTOR"].type == "array"
    assert fields["VECTOR"].items == {"type": "number"}
    assert fields["VECTOR"].constraints == {"minItems": 3, "maxItems": 3}
    assert fields["ESCAPED_VECTOR"].type == "array"
    assert fields["ESCAPED_VECTOR"].items == {"type": "number"}
    assert fields["ESCAPED_VECTOR"].constraints == {"minItems": 3, "maxItems": 3}
    assert fields["INLINE_DEFAULT"].type == "boolean"
    assert fields["INLINE_DEFAULT"].documented_default is False
    assert fields["CONST_VALUE"].constraints == {"const": 0.75}
    assert fields["DEFAULT_ITEMS"].documented_default == []
    assert fields["DEFAULT_OPTIONS"].documented_default == {}
    assert fields["DEFAULT_MODE"].documented_default == "FIRST"
    assert fields["REVERSED"].enum == [0, 1]
    assert fields["ENABLED"].type == "boolean"
    assert fields["ENABLED"].documented_default is False
    assert fields["ENABLED"].requirement == "optional"
    assert fields["LIMIT"].type == "number"
    assert fields["LIMIT"].documented_default == 0
    assert fields["LIMIT"].requirement == "required"

    draft_fields = {field["key"]: field for field in yaml.safe_load(ex.render_draft(section))["fields"]}
    assert draft_fields["NON_NEGATIVE"]["minimum"] == 0
    assert draft_fields["CODE"]["maxLength"] == 7
    assert draft_fields["VECTOR"]["items"]["type"] == "number"
    assert draft_fields["VECTOR"]["minItems"] == 3
    assert draft_fields["INLINE_DEFAULT"]["documentedDefault"] is False
    assert draft_fields["CONST_VALUE"]["const"] == 0.75
    assert draft_fields["DEFAULT_ITEMS"]["documentedDefault"] == []
    assert draft_fields["DEFAULT_OPTIONS"]["documentedDefault"] == {}
    assert draft_fields["DEFAULT_MODE"]["documentedDefault"] == "FIRST"


def test_only_exact_parallel_columns_are_split_into_independent_fields(tmp_path: Path):
    path = tmp_path / "99_DB_Parallel.md"
    path.write_text(
        """# 99 DB — Parallel

## 1. `/db/PARALLEL` — Parallel fields

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Exact pair | `"FIRST"` / `"SECOND"` | String / Integer | `"A"` / 2 | Optional / Required |
| 2 | Ambiguous pair | `"LEFT"` / `"RIGHT"` | String / Integer | - | Optional |
""",
        encoding="utf-8",
    )
    fields = ex.parse_chapter(path)[0].tables[0].fields
    by_key = {field.key: field for field in fields}

    assert {"FIRST", "SECOND"} <= set(by_key)
    assert by_key["FIRST"].type == "string"
    assert by_key["SECOND"].type == "integer"
    # One Required value beside two keys is not enough to assign it safely.
    assert 'LEFT" / "RIGHT' in by_key
    assert any("more than one" in note for note in by_key['LEFT" / "RIGHT'].notes)


@pytest.mark.parametrize(
    ("number", "key_cell", "expected"),
    [
        ("1", '"R" "G" "B"', ["R", "G", "B"]),
        ("(3)", '"FACTOR" / "CENT_F"', ["FACTOR", "CENT_F"]),
        ("(4)", '"DT" / "DB"', ["DT", "DB"]),
    ],
)
def test_literal_key_groups_with_shared_metadata_are_split(
    tmp_path: Path, number: str, key_cell: str, expected: list[str]
):
    """The manual's one-row homogeneous field shorthand preserves every key."""

    path = tmp_path / "99_DB_LiteralGroup.md"
    path.write_text(
        f"""## 1. `/db/GROUP` -- literal keys

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| {number} | Homogeneous values | {key_cell} | Number | 0 | Optional |
""",
        encoding="utf-8",
    )
    fields = ex.parse_chapter(path)[0].tables[0].fields
    assert [field.key for field in fields] == expected
    assert all(field.type == "number" and field.documented_default == 0 for field in fields)


def test_key_type_only_table_splits_quoted_literal_group_without_a_child_number(tmp_path: Path):
    """A three-column child table gives one homogeneous type for every literal key."""

    path = tmp_path / "99_DB_KeyTypeGroup.md"
    path.write_text(
        """## 1. `/db/GROUP` -- literal keys

| Key | Description | Value Type |
|---|---|---|
| `"RC_C1L1"`/`"RC_C1F1"`/`"RC_C1L2"`/`"RC_C1F2"` | Case values | Number |
""",
        encoding="utf-8",
    )

    fields = ex.parse_chapter(path)[0].tables[0].fields
    assert [field.key for field in fields] == ["RC_C1L1", "RC_C1F1", "RC_C1L2", "RC_C1F2"]
    assert all(field.type == "number" for field in fields)


def test_dotted_numbering_nests_children_under_the_documented_parent(tmp_path: Path):
    """The manual's 14.4.1 notation is a payload hierarchy, not a flat key list."""

    path = tmp_path / "99_DB_DottedNumbering.md"
    path.write_text(
        """## 1. `/db/DOTTED` -- dotted numbering

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 14 | Root | `"ROOT"` | Object | - | Optional |
| 14.4 | Child object | `"CHILD"` | Object | - | Optional |
| 14.4.1 | Leaf | `"LEAF"` | String | - | Required |
""",
        encoding="utf-8",
    )

    root = ex.parse_chapter(path)[0].tables[0].fields[0]
    assert root.key == "ROOT"
    assert [field.key for field in root.properties] == ["CHILD"]
    assert [field.key for field in root.properties[0].properties] == ["LEAF"]


def test_parenthesised_dash_numbering_nests_and_preserves_literal_conditions(tmp_path: Path):
    """``2-(N)`` rows are child payload fields, not independent root keys."""

    path = tmp_path / "99_DB_ParenthesisedNumbering.md"
    path.write_text(
        """## 1. `/db/PARENTHESISED` -- parenthesised numbering

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 2 | Mass control | `"MASS_CONTROL"` | Object | - | Required |
| 2-(1) | Type: `LUMPED` / `CONSISTENT` | `"MASS_TYPE"` | String (enum) | - | Required |
| 2-(2) | Position (`MASS_TYPE="LUMPED"`): `CENTROID` / `OFFSET` | `"MASS_POS"` | String (enum) | - | Conditional Required |
| 2-(3) | Convert self-weight | `"SELFWEIGHT"` | Boolean | - | Required |
| 2-(4) | Axis (`SELFWEIGHT=true`): `XYZ` / `XY` / `Z` | `"MASS_AXIS"` | String (enum) | - | Conditional Required |
""",
        encoding="utf-8",
    )

    root = ex.parse_chapter(path)[0].tables[0].fields[0]
    assert root.key == "MASS_CONTROL"
    assert [field.key for field in root.properties] == [
        "MASS_TYPE",
        "MASS_POS",
        "SELFWEIGHT",
        "MASS_AXIS",
    ]
    mass_type, mass_pos, _, mass_axis = root.properties
    assert mass_type.enum == ["LUMPED", "CONSISTENT"]
    assert mass_pos.enum == ["CENTROID", "OFFSET"]
    assert mass_pos.applies_when == [("MASS_TYPE", ("LUMPED",))]
    assert mass_axis.enum == ["XYZ", "XY", "Z"]
    assert mass_axis.applies_when == [("SELFWEIGHT", (True,))]


@pytest.mark.parametrize(
    ("manual_key", "contract_key"),
    [
        ('"POINT"[].ITEM"', "POINT[].ITEM"),
        ('"SPAN_BASE_ITEMS"[].ELEM_KEY"', "SPAN_BASE_ITEMS[].ELEM_KEY"),
    ],
)
def test_quoted_array_member_paths_are_transcribed_without_quote_characters(
    manual_key: str, contract_key: str
):
    assert ex._canonical_wire_property(manual_key) == contract_key


@pytest.mark.parametrize(
    ("property_schema", "expected"),
    [
        ({"enum": [0, 1]}, [0, 1]),
        ({"oneOf": [{"const": "LEFT"}, {"const": "RIGHT"}]}, ["LEFT", "RIGHT"]),
        ({"oneOf": [{"const": "D4"}, {"title": "remaining values"}]}, None),
    ],
)
def test_schema_enum_forms_only_accept_complete_literal_lists(property_schema: dict, expected: list | None):
    assert ex._schema_enum_values(property_schema) == expected


def test_endpoint_named_schema_wrapper_is_not_a_payload_property(tmp_path: Path):
    path = tmp_path / "99_DB_WrappedSchema.md"
    path.write_text(
        """## 1. `/db/WRAPPED` -- wrapped schema

### JSON Schema
```json
{"WRAPPED": {"type": "object", "properties": {"POINT": {"type": "array", "items": {"type": "object", "properties": {"ITEM": {"type": "number"}}}}}}}
```

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Point item | `"POINT"[].ITEM"` | Number | - | Optional |
""",
        encoding="utf-8",
    )
    field = ex.parse_chapter(path)[0].tables[0].fields[0]
    assert field.key == "POINT"
    assert field.type == "array"
    assert field.items == {"type": "object"}
    assert field.properties[0].key == "ITEM"
    assert not field.notes


@pytest.mark.parametrize(
    ("manual_type", "item_type", "length"),
    [
        ("Array[Number,21]", "number", 21),
        ("Array[Number, 6]", "number", 6),
        ("Array[Integer,2]", "integer", 2),
        ("Array[Boolean,6]", "boolean", 6),
        ("Array[Object,3]", "object", 3),
    ],
)
def test_fixed_length_array_forms_are_transcribed_without_nesting(
    manual_type: str, item_type: str, length: int
):
    assert ex._normalize_type(manual_type) == ("array", {"type": item_type}, None)
    assert ex._type_constraints(manual_type) == {"minItems": length, "maxItems": length}


def test_array_item_type_with_a_minimum_count_suffix_is_transcribed():
    """NLCT-M1 states both Number items and a one-item minimum in one cell."""
    manual_type = "Array [Number] (≥1개)"

    assert ex._normalize_type(manual_type) == ("array", {"type": "number"}, None)
    assert ex._type_constraints(manual_type) == {"minItems": 1}


def test_compact_object_arrays_and_literal_type_cells_are_transcribed_without_guessing():
    assert ex._normalize_type("Array[{PY, PZ}]") == ("array", {"type": "object"}, None)
    assert ex._normalize_type('"KDS(41-17-00:2019)"') == ("string", None, None)
    assert ex._type_constraints('"KDS(41-17-00:2019)"') == {"const": "KDS(41-17-00:2019)"}
    field_type, _, note = ex._normalize_type("Object (oneOf)")
    assert field_type == "object"
    assert "does not state" in note


def test_report_prints_measured_stage_two_blockers(section: ex.Section, capsys: pytest.CaptureFixture[str]):
    assert ex.run_report([section], {}) == 0
    output = capsys.readouterr().out
    assert "Stage 2 fidelity blockers:" in output
    assert "promotion-note forms (field occurrences):" in output
    assert "conditional requirement has no stated condition" in output
    assert "non-literal System default kept verbatim" in output
    assert "supplementary tables:" in output
    assert "unmerged supplementary tables by manual selector evidence:" in output


def test_report_measures_table_contract_coverage(section: ex.Section, capsys: pytest.CaptureFixture[str]):
    assert ex.run_report([section], {"18_POST_PreProcess.md": 10}) == 0
    output = capsys.readouterr().out
    assert "table-contract coverage:" in output
    assert "/post/PM and /post/STEELCODECHECK) are read as endpoint sections" in output


def test_a_table_family_chapter_yields_only_its_own_route_sections(tmp_path: Path):
    chapter = tmp_path / "23_POST_Design.md"
    chapter.write_text(
        "\n".join([
            "# Design",
            "",
            "## 공통 사항 (Design Forces 테이블, #3~#10)",
            "",
            "### Input URI",
            "",
            "```",
            "{base url}/post/TABLE",
            "```",
            "",
            "## 1. Steel Code Check",
            "",
            "### Input URI",
            "",
            "```",
            "{base url}/post/STEELCODECHECK",
            "```",
            "",
            "### Active Methods",
            "",
            "`POST`",
            "",
            "## 2. Beam Design Forces",
            "",
            "### Input URI",
            "",
            "```",
            "{base url}/post/TABLE",
            "```",
            "",
            "### Active Methods",
            "",
            "`POST`",
        ]) + "\n",
        encoding="utf-8",
    )

    sections = ex.parse_chapter(chapter, own_routes_only=True)

    assert [section.endpoint for section in sections] == ["/post/STEELCODECHECK"]
    only = sections[0]
    assert only.methods == ["POST"]
    # The contract cites the manual's own heading, not the rewritten one.
    assert only.heading == "1. Steel Code Check"
    assert only.title == "Steel Code Check"
    # Nothing from the shared-table section after it leaks into the body.
    assert not any("Beam Design Forces" in line for line in only.lines)


def test_report_separates_resources_with_no_parsed_manual_section(
    section: ex.Section, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    inventory = tmp_path / "schema"
    endpoints = tmp_path / "contracts" / "endpoints"
    drafts = tmp_path / "contracts" / "drafts"
    inventory.mkdir()
    endpoints.mkdir(parents=True)
    drafts.mkdir(parents=True)
    (inventory / "typescript-resources.json").write_text(
        json.dumps({"resources": [{"endpoint": "/db/SYNTH"}, {"endpoint": "/db/NOSECTION"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(ex, "ROOT", tmp_path)
    monkeypatch.setattr(ex, "ENDPOINT_DIR", endpoints)
    monkeypatch.setattr(ex, "DRAFT_DIR", drafts)

    assert ex.run_report([section], {}) == 0
    output = capsys.readouterr().out
    assert "1 without a parsed manual section." in output
    assert "/db/NOSECTION" in output


SHARED_ROUTE_CHAPTER = """# 98 Design — Synthetic shared route

## 1. `/DESIGN/SYN/TABLE` — Alpha Forces (알파 설계력)

> **공유 URI:** 1·2·3번은 동일한 URI를 사용하며 `TABLE_TYPE` 값으로만 구분됩니다.

- **Methods**: `POST`

### 파라미터

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Table title | `"TABLE_NAME"` | String | - | Optional |
| 2 | Table type (fixed `"ALPHAFORCES"`) | `"TABLE_TYPE"` | String (enum) | - | Required |
| 3 | Export path | `"EXPORT_PATH"` | String | - | Optional |

## 2. `/DESIGN/SYN/TABLE` — Beta Forces (베타 설계력)

- **Methods**: `POST`

### 파라미터

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Table title | `"TABLE_NAME"` | String | - | Optional |
| 2 | Table type (fixed `"BETAFORCES"`) | `"TABLE_TYPE"` | String (enum) | - | Required |
| 3 | Export path | `"EXPORT_PATH"` | String | - | Optional |

## 3. `/DESIGN/SYN/TABLE` — Gamma Forces (감마 설계력)

- **Methods**: `POST`

### 파라미터

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Table title | `"TABLE_NAME"` | String | - | Optional |
| 2 | Table type (fixed `"GAMMAFORCES"`) | `"TABLE_TYPE"` | String (enum) | - | Required |
| 3 | Export path | `"EXPORT_PATH"` | String | - | Optional |
"""


def _shared_route_sections(tmp_path: Path, chapter: str = SHARED_ROUTE_CHAPTER) -> list[ex.Section]:
    path = tmp_path / "98_Design_Synthetic.md"
    path.write_text(chapter, encoding="utf-8")
    return ex.parse_chapter(path)


def test_sections_sharing_one_route_fold_into_one_with_the_values_unioned(tmp_path: Path):
    """Three manual sections, one URI: the contract must be one endpoint.

    The RC design chapter documents /DESIGN/RC/KDS-41-20-2022/TABLE once per
    result table and says the sections differ only by Argument.TABLE_TYPE.
    Emitted apart they overwrote each other; emitted as three ids they would
    invent two routes.
    """
    sections = _shared_route_sections(tmp_path)
    assert [s.title for s in sections] == [
        "Alpha Forces (알파 설계력)",
        "Beta Forces (베타 설계력)",
        "Gamma Forces (감마 설계력)",
    ]

    merged = ex.merge_shared_endpoint_sections(sections)
    assert len(merged) == 1
    folded = merged[0]
    assert folded.endpoint == "/DESIGN/SYN/TABLE"

    by_key = {field.key: field for field in folded.tables[0].fields}
    assert by_key["TABLE_TYPE"].enum == ["ALPHAFORCES", "BETAFORCES", "GAMMAFORCES"]
    # Each section calls its own value fixed. Keep all three claims rather than
    # writing "one of three", which is a thing the manual never says.
    assert by_key["TABLE_TYPE"].description.count("fixed") == 3
    assert by_key["TABLE_NAME"].description == "Table title"

    assert [heading.split(".")[0] for heading, _ in folded.merged_sections] == ["1", "2", "3"]
    assert [line for _, line in folded.merged_sections] == sorted(
        line for _, line in folded.merged_sections
    )


def test_a_folded_route_emits_one_draft_naming_every_section_it_came_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    endpoints = tmp_path / "contracts" / "endpoints"
    drafts = tmp_path / "contracts" / "drafts"
    endpoints.mkdir(parents=True)
    monkeypatch.setattr(ex, "ROOT", tmp_path)
    monkeypatch.setattr(ex, "ENDPOINT_DIR", endpoints)
    monkeypatch.setattr(ex, "DRAFT_DIR", drafts)
    monkeypatch.setattr(ex, "live_omission_evidence", dict)

    merged = ex.merge_shared_endpoint_sections(_shared_route_sections(tmp_path))
    assert ex.run_emit(merged, [], emit_all=True) == 0

    captured = capsys.readouterr()
    assert "WARNING" not in captured.err
    assert "wrote 1 draft(s)" in captured.out

    text = (drafts / "design-syn-table.yaml").read_text(encoding="utf-8")
    assert "name: Alpha Forces / Beta Forces / Gamma Forces" in text
    assert "enum: [ALPHAFORCES, BETAFORCES, GAMMAFORCES]" in text
    assert "  mergedSections:" in text
    assert text.count("    - heading:") == 3


def test_a_route_whose_value_is_only_named_in_prose_folds_without_inventing_an_enum(
    tmp_path: Path,
):
    """The SRC chapter writes the selector into the description, not a column.

    Folding still has to happen - one URI is one endpoint - but the values it
    never parsed as an enum must not appear as one. Both descriptions survive
    so a reviewer can supply the enum from what the manual actually wrote.
    """
    chapter = SHARED_ROUTE_CHAPTER.replace(
        'Table type (fixed `"ALPHAFORCES"`) | `"TABLE_TYPE"` | String (enum)',
        "Table type - one of: `ALPHAFORCES` | `\"TABLE_TYPE\"` | String",
    ).replace(
        'Table type (fixed `"BETAFORCES"`) | `"TABLE_TYPE"` | String (enum)',
        "Table type - one of: `BETAFORCES` | `\"TABLE_TYPE\"` | String",
    ).replace(
        'Table type (fixed `"GAMMAFORCES"`) | `"TABLE_TYPE"` | String (enum)',
        "Table type - one of: `GAMMAFORCES` | `\"TABLE_TYPE\"` | String",
    )
    merged = ex.merge_shared_endpoint_sections(_shared_route_sections(tmp_path, chapter))
    assert len(merged) == 1

    table_type = {f.key: f for f in merged[0].tables[0].fields}["TABLE_TYPE"]
    assert table_type.enum == []
    for value in ("ALPHAFORCES", "BETAFORCES", "GAMMAFORCES"):
        assert value in table_type.description


def test_sections_disagreeing_about_more_than_one_field_are_left_unfolded(tmp_path: Path):
    """Two documents about one endpoint is a question for a person.

    /ope/GSBG is the live case: two chapters transcribe the same endpoint, one
    with inline conditional requirements and one with bold variant headers.
    Averaging them would publish a request shape neither chapter states.
    """
    chapter = SHARED_ROUTE_CHAPTER.replace(
        "| 3 | Export path | `\"EXPORT_PATH\"` | String | - | Optional |\n\n## 2.",
        "| 3 | Export path | `\"EXPORT_PATH\"` | String | - | Required |\n\n## 2.",
    )
    sections = _shared_route_sections(tmp_path, chapter)
    assert ex.merge_shared_endpoint_sections(sections) == sections


def test_emit_warns_when_two_manual_sections_share_a_draft_name(
    section: ex.Section,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """Two sections, one draft name: the later one wins and must say so.

    A chapter that repeats another chapter's endpoint, and an endpoint
    documented once per result table, both land here. Overwriting is
    tolerable; overwriting in silence is not - the only symptom used to be a
    written count larger than the number of files on disk.
    """
    endpoints = tmp_path / "contracts" / "endpoints"
    drafts = tmp_path / "contracts" / "drafts"
    endpoints.mkdir(parents=True)
    monkeypatch.setattr(ex, "ROOT", tmp_path)
    monkeypatch.setattr(ex, "ENDPOINT_DIR", endpoints)
    monkeypatch.setattr(ex, "DRAFT_DIR", drafts)
    monkeypatch.setattr(ex, "live_omission_evidence", dict)

    repeat = dataclasses.replace(
        section,
        chapter_file="17_DB_Bridge.md",
        number="5",
        title="Repeated In Another Chapter",
        tables=[
            dataclasses.replace(section.tables[0], fields=section.tables[0].fields[:-1]),
            *section.tables[1:],
        ],
    )
    # Folding is tried first and refuses these: they disagree about the field
    # list itself, not about one enumerated value. What is left is the warning.
    assert ex.merge_shared_endpoint_sections([section, repeat]) == [section, repeat]
    assert ex.run_emit([section, repeat], [], emit_all=True) == 0

    captured = capsys.readouterr()
    assert [path.name for path in drafts.glob("*.yaml")] == ["db-synth.yaml"]
    assert "wrote 1 draft(s)" in captured.out
    assert "1 further section(s) reused a draft name" in captured.out
    assert "WARNING: /db/SYNTH" in captured.err
    assert (
        f"{section.chapter_file} section {section.number} was overwritten "
        "by 17_DB_Bridge.md section 5"
    ) in captured.err
    # Windows consoles are cp949 and stderr is not reconfigured, so a manual
    # title in this message would crash the run it is trying to explain.
    assert captured.err.isascii()
    assert "Repeated In Another Chapter" in (drafts / "db-synth.yaml").read_text(encoding="utf-8")


def test_conditional_variant_tables_are_reported_not_merged(section: ex.Section):
    assert len(section.tables) == 2
    assert [(variant.field, variant.equals) for variant in section.variants] == [("TYPE", "SPECIAL")]
    main_keys = {f.key for f in section.tables[0].fields}

    assert "SPECIAL" not in main_keys
    assert section.tables[1].heading == "TYPE=SPECIAL 전용"


@pytest.mark.parametrize(
    ("endpoint", "extra_headings", "expected"),
    [
        pytest.param(
            "/db/CCFC",
            ['Constant 타입 (TYPE="CONST")', 'User 타입 (TYPE="USER")'],
            [("CONST_FIELD", [("TYPE", "CONST")]), ("USER_FIELD", [("TYPE", "USER")])],
            id="exclusive-string-type-tables",
        ),
        pytest.param(
            "/db/ETFC",
            ['Constant 타입 (TYPE="CONST")', 'Sine 타입 (TYPE="SINE")', 'User 타입 (TYPE="USER")'],
            [
                ("CONST_FIELD", [("TYPE", "CONST")]),
                ("SINE_FIELD", [("TYPE", "SINE")]),
                ("USER_FIELD", [("TYPE", "USER")]),
            ],
            id="three-way-exclusive-string-type-tables",
        ),
        pytest.param(
            "/db/PNLA",
            ['ELEM_TYPE = "PLATE"', 'SELECT_TYPE = "IN_GROUP"', 'ELEM_TYPE = "SOLID"'],
            [
                ("PLATE_FIELD", [("ELEM_TYPE", "PLATE")]),
                ("GROUP_FIELD", [("SELECT_TYPE", "IN_GROUP")]),
                ("SOLID_FIELD", [("ELEM_TYPE", "SOLID")]),
            ],
            id="independent-string-selector-tables",
        ),
        pytest.param(
            "/db/THFC",
            ["Time Function (FUNCTYPE=1)", "Sinusoidal (FUNCTYPE=2)"],
            [("TIME_FIELD", [("FUNCTYPE", 1)]), ("SINE_FIELD", [("FUNCTYPE", 2)])],
            id="exclusive-integer-type-tables",
        ),
        pytest.param(
            "/db/NLNK",
            [
                "REF_SYSTEM=0 (element)",
                "REF_SYSTEM=1 (global) - angle",
                "REF_SYSTEM=1 (global) - 3Points",
                "REF_SYSTEM=1 (global) - vector",
            ],
            [
                ("ELEMENT_FIELD", [("REF_SYSTEM", 0)]),
                ("ANGLE_FIELD", [("REF_SYSTEM", 1), ("INPUT_METHOD", 0)]),
                ("POINTS_FIELD", [("REF_SYSTEM", 1), ("INPUT_METHOD", 1)]),
                ("VECTOR_FIELD", [("REF_SYSTEM", 1), ("INPUT_METHOD", 2)]),
            ],
            id="nested-integer-selectors-use-and-semantics",
        ),
        pytest.param(
            "/db/HSFC",
            [
                'Constant (TYPE="CONST")',
                'Code (TYPE="FUNC", OPT_USE_CONC_DATA=false)',
                'Code (TYPE="FUNC", OPT_USE_CONC_DATA=true)',
                'User (TYPE="USER")',
            ],
            [
                ("CONST_FIELD", [("TYPE", "CONST")]),
                ("FUNC_FALSE_FIELD", [("TYPE", "FUNC"), ("OPT_USE_CONC_DATA", False)]),
                ("FUNC_TRUE_FIELD", [("TYPE", "FUNC"), ("OPT_USE_CONC_DATA", True)]),
                ("USER_FIELD", [("TYPE", "USER")]),
            ],
            id="nested-boolean-selector-tables",
        ),
    ],
)
def test_audited_conditional_table_forms_keep_source_text_and_structured_conditions(
    endpoint: str,
    extra_headings: list[str],
    expected: list[tuple[str, list[tuple[str, str | int]]]],
):
    base = ex.ParsedField("BASE", "Base", "string", None, "required", None)
    tables = [ex.ParsedTable("Base", 1, [base])]
    for index, heading in enumerate(extra_headings, 1):
        key = expected[index - 1][0]
        field = ex.ParsedField(key, key, "number", None, "required", None)
        tables.append(ex.ParsedTable(heading, index + 1, [field]))
    section = ex.Section("manual.md", "1", endpoint, endpoint, endpoint, [], tables=tables)

    fields, resolved = ex._conditional_fields(section, [base])

    assert resolved == set(range(1, len(tables)))
    by_key = {field.key: field for field in fields}
    for key, conditions in expected:
        expected_conditions = [(path, (v,) if not isinstance(v, tuple) else v) for path, v in conditions]
        assert by_key[key].applies_when == expected_conditions
        assert by_key[key].condition


def test_stct_conditional_tables_keep_multi_value_and_accumulative_selectors():
    """STCT's last two table headings state the exact root-field gates."""
    base = ex.ParsedField("BASE", "Base", "string", None, "required", None)
    fillers = [ex.ParsedTable(f"Filler {index}", index, []) for index in range(1, 5)]
    nonlinear = ex.ParsedField("NONLINEAR", "Nonlinear", "number", None, "optional", None)
    time_effect = ex.ParsedField("TIME_EFFECT", "Time", "number", None, "optional", None)
    tables = [
        ex.ParsedTable("Base", 0, [base]),
        *fillers,
        ex.ParsedTable("Nonlinear", 5, [nonlinear]),
        ex.ParsedTable("Time dependent", 6, [time_effect]),
    ]
    section = ex.Section("manual.md", "1", "/db/STCT", "STCT", "STCT", [], tables=tables)

    fields, resolved = ex._conditional_fields(section, [base])
    by_key = {field.key: field for field in fields}

    assert resolved == {5, 6}
    assert by_key["NONLINEAR"].applies_when == [("iINC_NLA", (1, 2))]
    assert by_key["TIME_EFFECT"].applies_when == [("iNLA_TYPE", (1,))]


@pytest.mark.parametrize(
    ("parent_type", "expect_child"),
    [
        pytest.param("Array[Object]", True, id="dash-row-after-array-is-an-item-property"),
        pytest.param("Object", False, id="dash-row-after-non-array-is-not-inferred"),
    ],
)
def test_dash_number_row_only_nests_under_an_explicit_array(parent_type: str, expect_child: bool, tmp_path: Path):
    """The manual's dash marker is structural only with its Array parent."""
    path = tmp_path / "99_DB_DashArray.md"
    path.write_text(
        "## 1. `/db/DASH-ARRAY` -- dash array rows\n\n"
        "| No. | Description | Key | Value Type | Default | Required |\n"
        "|---|---|---|---|---|---|\n"
        f'| 1 | Values | `ITEM` | {parent_type} | - | Required |\n'
        "| 2 | - Time | `TIME` | Number | - | Required |\n",
        encoding="utf-8",
    )

    fields = ex.parse_chapter(path)[0].tables[0].fields
    if expect_child:
        assert [field.key for field in fields] == ["ITEM"]
        assert [field.key for field in fields[0].properties] == ["TIME"]
    else:
        assert [field.key for field in fields] == ["ITEM", "TIME"]


def test_conditional_array_table_merges_only_into_its_named_item_path():
    """MVLDid's Auto table extends SUB_LOAD_ITEMS; it never creates root keys."""
    base_item = ex.ParsedField("BASE", "base", "string", None, "required", None)
    sub_load_items = ex.ParsedField("SUB_LOAD_ITEMS", "items", "array", {"type": "object"}, "required", None)
    sub_load_items.properties = [base_item]
    auto_sub_load_items = ex.ParsedField("SUB_LOAD_ITEMS", "items", "array", {"type": "object"}, "required", None)
    auto_extra = ex.ParsedField("VEHICLE_CLASS_2", "auto-only", "string", None, "required", None)
    auto_sub_load_items.properties = [auto_extra]
    tables = [
        ex.ParsedTable("Parameters", 1, [sub_load_items]),
        ex.ParsedTable("Auto Live Load Combinations", 2, [
            ex.ParsedField("NUM_LOADED_LANES", "count", "integer", None, "required", None),
            auto_sub_load_items,
        ]),
        ex.ParsedTable("Permit Vehicle", 3, [
            ex.ParsedField("PERMIT_VEHICLE", "permit", "integer", None, "required", None),
        ]),
    ]
    section = ex.Section("manual.md", "1", "/db/MVLDid", "Moving Load Cases – India", "manual", [], tables=tables)

    fields, resolved = ex._conditional_fields(section, tables[0].fields)

    assert resolved == {1, 2}
    assert [field.key for field in fields] == ["SUB_LOAD_ITEMS", "PERMIT_VEHICLE"]
    child = fields[0].properties[1]
    assert child.key == "VEHICLE_CLASS_2"
    assert child.applies_when == [("OPT_AUTO_LL", (True,))]
    assert fields[1].applies_when == [("OPT_LC_FOR_PERMIT_LOAD", (True,))]


def test_nspr_type_tables_merge_into_items_and_widen_shared_direction_fields():
    """The three named spring types share DIR/DV without flattening ITEMS."""
    spring_type = ex.ParsedField("TYPE", "type", "string", None, "required", None)
    items = ex.ParsedField("ITEMS", "items", "array", {"type": "object"}, "required", None)
    items.properties = [spring_type]
    linear = ex.ParsedField("SDR", "linear", "array", {"type": "number"}, "required", None)
    comp_dir = ex.ParsedField("DIR", "direction", "integer", None, "required", None)
    comp_dv = ex.ParsedField("DV", "vector", "array", {"type": "number"}, "optional", 0)
    multi_dir = ex.ParsedField("DIR", "direction", "integer", None, "required", None)
    multi_dv = ex.ParsedField("DV", "vector", "array", {"type": "number"}, "optional", 0)
    tables = [
        ex.ParsedTable("Base", 0, [items]),
        ex.ParsedTable("LINEAR", 1, [linear]),
        ex.ParsedTable("COMP/TENS", 2, [comp_dir, comp_dv]),
        ex.ParsedTable("MULTI", 3, [multi_dir, multi_dv]),
    ]
    section = ex.Section("manual.md", "1", "/db/NSPR", "NSPR", "NSPR", [], tables=tables)

    fields, resolved = ex._conditional_fields(section, [items])
    children = {field.key: field for field in fields[0].properties}

    assert resolved == {1, 2, 3}
    assert children["SDR"].applies_when == [("TYPE", ("LINEAR",))]
    assert children["DIR"].applies_when == [("TYPE", ("COMP", "TENS", "MULTI"))]
    assert children["DV"].applies_when == [
        ("TYPE", ("COMP", "TENS", "MULTI")),
        ("DIR", (6,)),
    ]


def test_nspr_surface_function_table_merges_into_items_with_form_type_gate():
    """The heading states FormType=1 and /info places both fields in ITEMS."""
    form_type = ex.ParsedField("FormType", "form", "integer", None, "optional", 0)
    items = ex.ParsedField("ITEMS", "items", "array", {"type": "object"}, "required", None)
    items.properties = [form_type]
    fillers = [ex.ParsedTable(f"Filler {index}", index, []) for index in range(1, 4)]
    effarea = ex.ParsedField("EFFAREA", "width", "number", None, "optional", 0)
    dk = ex.ParsedField("DK", "modulus", "array", {"type": "number"}, "optional", 0)
    tables = [
        ex.ParsedTable("Base", 0, [items]),
        *fillers,
        ex.ParsedTable("Surface function", 4, [effarea, dk]),
    ]
    section = ex.Section("manual.md", "1", "/db/NSPR", "NSPR", "NSPR", [], tables=tables)

    fields, resolved = ex._conditional_fields(section, [items])
    children = {field.key: field for field in fields[0].properties}

    assert 4 in resolved
    assert children["EFFAREA"].applies_when == [("FormType", (1,))]
    assert children["DK"].applies_when == [("FormType", (1,))]


def test_impf_factor_tables_merge_into_items_and_keep_parts_element_gate():
    """IMPF widens shared item fields and keeps PARTS off the Truss branch."""
    items = ex.ParsedField("ITEMS", "items", "array", {"type": "object"}, "required", None)
    common_id = ex.ParsedField("ID", "id", "integer", None, "required", None)
    user_factor = ex.ParsedField("FACTOR", "factor", "number", None, "required", None)
    auto_id = ex.ParsedField("ID", "id", "integer", None, "required", None)
    element_type = ex.ParsedField("ELEMTYPE", "element", "string", None, "required", None)
    parts = ex.ParsedField("PARTS", "parts", "array", {"type": "boolean"}, "conditional", None)
    parts.condition = "Beam/Plate만"
    tables = [
        ex.ParsedTable("Base", 0, [items]),
        ex.ParsedTable("User", 1, [common_id, user_factor]),
        ex.ParsedTable("Auto", 2, [auto_id, element_type, parts]),
    ]
    section = ex.Section("manual.md", "1", "/db/IMPF", "IMPF", "IMPF", [], tables=tables)

    fields, resolved = ex._conditional_fields(section, [items])
    children = {field.key: field for field in fields[0].properties}

    assert resolved == {1, 2}
    assert children["ID"].applies_when == [
        ("FACT_TYPE", ("IMPACT_FACT", "EFF_SPAN_LEN_USER", "EFF_SPAN_LEN_AUTO"))
    ]
    assert children["FACTOR"].applies_when == [
        ("FACT_TYPE", ("IMPACT_FACT", "EFF_SPAN_LEN_USER"))
    ]
    assert children["ELEMTYPE"].applies_when == [("FACT_TYPE", ("EFF_SPAN_LEN_AUTO",))]
    assert children["PARTS"].applies_when == [
        ("FACT_TYPE", ("EFF_SPAN_LEN_AUTO",)),
        ("ELEMTYPE", ("BEAM", "PLATE")),
    ]


def test_nlct_m1_tables_preserve_required_and_applicable_branch_claims(
    tmp_path: Path,
):
    """LOAD_STEPS and ADVANCED keep the exact strength of each manual claim."""
    path = tmp_path / "12_DB_Analysis_Control.md"
    path.write_text(
        '''## 16. `/db/NLCT-M1` -- nonlinear control

### Parameters — 공통
| Key | Value Type | Default | Required |
|---|---|---|---|
| `LOAD_STEPS` | Object | - | Required |
| `ADVANCED` | Object | - | Optional |

### Parameters — LOAD_STEPS 객체
| Key | Value Type | Default | Description |
|---|---|---|---|
| `STEP_MODE` | String (enum: `"AUTO"`/`"MANUAL"`) | - | 스텝 모드 (Required) |
| `NUMBER_STEPS` | Integer (≥1) | 1 | 스텝 수 (`STEP_MODE="AUTO"`일 때 필수) |
| `MANUAL_STEPS` | Array [Number] (≥1개) | - | 사용자 정의 스텝 목록 (`STEP_MODE="MANUAL"`일 때) |
| `MAX_DISP` | Number (0 금지) | - | (`ITER_METHOD="DISP"`) 최대 변위 — 명시적 값 필수 |
| `REF_NODE` | Object | - | (`ITER_METHOD="DISP"`) 기준 절점 — 하위 `OPT_USE`(Boolean, Required)/`NODE`(Integer, `OPT_USE=false`시 기본 0) |

### Parameters — CONV_CRITERIA 객체
| Key | Value Type | Default | Description |
|---|---|---|---|
| `OPT_USE` | Boolean | - | use |

### Parameters — ADVANCED 객체 (고급 비선형 설정, 전체 Optional — 미지정 시 서버 기본값 사용)
| Key | Value Type | Default | Description |
|---|---|---|---|
| `OPT_USE_DEFAULT` | Boolean | - | 기본 설정 사용 여부 (Required — true면 아래 필드 모두 미지정 허용) |
| `MAX_ITER_PER_INCREMENT` | Integer | 50 | 증분당 최대 반복 횟수 |
''',
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    fields, resolved = ex._structural_fields(section)

    assert [merge.table for merge in resolved] == [1, 3]
    load_steps = next(field for field in fields if field.key == "LOAD_STEPS")
    load_by_key = {field.key: field for field in load_steps.properties}
    assert load_by_key["STEP_MODE"].requirement == "required"
    assert load_by_key["NUMBER_STEPS"].requirement == "conditional"
    assert load_by_key["NUMBER_STEPS"].applies_when == [("STEP_MODE", ("AUTO",))]
    assert load_by_key["MANUAL_STEPS"].requirement is None
    assert load_by_key["MANUAL_STEPS"].applies_when == [("STEP_MODE", ("MANUAL",))]
    assert load_by_key["MANUAL_STEPS"].items == {"type": "number"}
    assert load_by_key["MANUAL_STEPS"].constraints == {"minItems": 1}
    assert load_by_key["MAX_DISP"].requirement == "conditional"
    assert load_by_key["MAX_DISP"].applies_when == [("ITER_METHOD", ("DISP",))]
    assert [(field.key, field.requirement) for field in load_by_key["REF_NODE"].properties] == [
        ("OPT_USE", "required"),
        ("NODE", None),
    ]
    advanced = next(field for field in fields if field.key == "ADVANCED")
    assert [(field.key, field.requirement) for field in advanced.properties] == [
        ("OPT_USE_DEFAULT", "required"),
        ("MAX_ITER_PER_INCREMENT", "optional"),
    ]


def test_structural_table_merge_uses_the_manual_named_object_path(tmp_path: Path):
    """A structural table goes below TCELEM, never beside it at record root."""
    path = tmp_path / "99_DB_Structural.md"
    path.write_text(
        """## 1. `/db/ACTL-M1` -- control

### Base
| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Truss options | `"TCELEM"` | Object | - | Optional |

### TCELEM object
| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Increment count | `"NUMINC"` | Integer | 1 | Optional |
| 2 | Convergence | `"CONVERGENCE"` | Object | - | Optional |

### CONVERGENCE object
| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Use criterion | `"OPT_USE"` | Boolean | false | Optional |
""",
        encoding="utf-8",
    )
    draft = yaml.safe_load(ex.render_draft(ex.parse_chapter(path)[0]))
    tcelem = draft["fields"][0]
    assert [field["key"] for field in tcelem["properties"]] == ["NUMINC", "CONVERGENCE"]
    assert tcelem["properties"][1]["properties"][0]["key"] == "OPT_USE"
    assert "unmergedTables" not in draft["extraction"]
    assert draft["extraction"]["structuralTables"][0]["paths"] == ["TCELEM"]


@pytest.mark.parametrize(
    ("endpoint", "base_rows", "extra_heading", "extra_rows", "table_index", "expected_path"),
    [
        (
            "/db/ELEM",
            '| 1 | Element type | `TYPE` | String | `"BEAM"` | Optional |',
            "Beam, Truss, Plane Strain, Axisymmetric",
            '| 2 | Beta angle | `ANGLE` | Number | 0 | Optional |',
            1,
            ("ANGLE",),
        ),
        (
            "/db/STCT",
            '| 1 | Analysis type | `iINC_NLA` | Integer | 0 | Optional |',
            "Parameters — Cable-Pretension / Initial Force Control",
            '| 2 | Cable force type | `CPFC` | String | `"INTERNAL"` | Optional |',
            2,
            ("CPFC",),
        ),
        (
            "/db/STCT",
            '| 1 | Analysis type | `iINC_NLA` | Integer | 0 | Optional |',
            "Parameters — Initial Displacement / Camber / 기타",
            '| 2 | Initial tangent displacement | `bITD` | Boolean | false | Optional |',
            3,
            ("bITD",),
        ),
        (
            "/db/STCT",
            '| 1 | Analysis type | `iINC_NLA` | Integer | 0 | Optional |',
            "Parameters — Linear & Independent Stage",
            "\n".join(
                [
                    '| 2 | Include P-Delta | `bINC_PDL` | Boolean | false | Optional |',
                    '| 3 | Iterations | `iITER` | Integer | - | Optional |',
                    '| 4 | Tolerance | `TOL` | Number | - | Optional |',
                ]
            ),
            4,
            ("TOL",),
        ),
    ],
    ids=[
        "elem-root-subtype-row",
        "stct-root-cable-controls",
        "stct-root-displacement-controls",
        "stct-root-mode-table",
    ],
)
def test_reviewed_single_object_tables_merge_at_info_path(
    tmp_path: Path,
    endpoint: str,
    base_rows: str,
    extra_heading: str,
    extra_rows: str,
    table_index: int,
    expected_path: tuple[str, ...],
):
    """A reviewed one-object table is placed exactly where /info reports it."""
    path = tmp_path / "99_DB_InfoPlaced.md"
    filler_tables = "\n".join(
        f"""### Unrelated table {index}

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Unrelated | `UNRELATED_{index}` | Number | - | Optional |
"""
        for index in range(1, table_index)
    )
    path.write_text(
        f"""## 1. `{endpoint}` — info-placed table

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
{base_rows}

{filler_tables}
### {extra_heading}

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
{extra_rows}
""",
        encoding="utf-8",
    )

    draft = yaml.safe_load(ex.render_draft(ex.parse_chapter(path)[0]))
    field: dict = {entry["key"]: entry for entry in draft["fields"]}[expected_path[0]]
    for segment in expected_path[1:]:
        field = {entry["key"]: entry for entry in field["properties"]}[segment]
    assert field["key"] == expected_path[-1]
    unmerged = draft["extraction"].get("unmergedTables", [])
    assert extra_heading not in {entry["heading"] for entry in unmerged}


def test_reviewed_nested_info_container_keeps_unknown_requiredness(tmp_path: Path):
    """A heading-named container gets /info nesting but no invented optionality."""
    path = tmp_path / "09_DB_Dynamic_Loads.md"
    filler_tables = "\n".join(
        f"""### Unrelated table {index}

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Unrelated | `UNRELATED_{index}` | Number | - | Optional |
"""
        for index in range(1, 8)
    )
    path.write_text(
        f"""## 1. `/db/THIS-M1` — time history

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Nonlinear control | `NONL_CTRL_PARAM` | Object | - | Optional |
| (2) | Iteration control | `ITER_CTRL` | Object | - | Required |

{filler_tables}
### Boundary nonlinear analysis (`BOUNDARY_NL_ANAL`)

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Method | `METHOD` | Integer | 0 | Optional |
| 2 | Tolerance | `TOL` | Number | 1e-08 | Optional |
""",
        encoding="utf-8",
    )

    draft = yaml.safe_load(ex.render_draft(ex.parse_chapter(path)[0]))
    nonl = {entry["key"]: entry for entry in draft["fields"]}["NONL_CTRL_PARAM"]
    iteration = {entry["key"]: entry for entry in nonl["properties"]}["ITER_CTRL"]
    container = {entry["key"]: entry for entry in iteration["properties"]}["BOUNDARY_NL_ANAL"]
    assert container["requirement"] == "unstated"
    assert container["documentedOptional"] is None
    assert [entry["key"] for entry in container["properties"]] == ["METHOD", "TOL"]
    unmerged = draft["extraction"].get("unmergedTables", [])
    assert "Boundary nonlinear analysis (`BOUNDARY_NL_ANAL`)" not in {
        entry["heading"] for entry in unmerged
    }


def test_this_m1_reviewed_table_mapping_keeps_the_measured_full_path():
    merge = ex._STRUCTURAL_TABLE_SPLITS["/db/THIS-M1"][0]
    assert merge.table == 8
    assert merge.targets == (("NONL_CTRL_PARAM", "ITER_CTRL", "BOUNDARY_NL_ANAL"),)
    assert ex._STRUCTURAL_CONTAINER_PATHS["/db/THIS-M1"] == merge.targets


def test_product_partition_stays_on_fields_not_the_endpoint(tmp_path: Path):
    path = tmp_path / "99_DB_ProductSplit.md"
    path.write_text(
        """## 1. `/db/IEHC` -- hinge control

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Beam | `"BEAM"` | Boolean | false | Optional |

### GEN-only fields
| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 2 | Wall | `"WALL"` | Boolean | false | Optional |
""",
        encoding="utf-8",
    )
    draft = yaml.safe_load(ex.render_draft(ex.parse_chapter(path)[0]))
    fields = {field["key"]: field for field in draft["fields"]}
    assert fields["WALL"]["products"] == ["gen"]
    assert "products" not in fields["BEAM"]


def test_explicit_variant_tables_preserve_their_discriminator_and_do_not_merge(tmp_path: Path):
    path = tmp_path / "99_DB_Variants.md"
    path.write_text(
        """# 99 DB — Variants

## 1. `/db/VARIANT` — Explicit variants

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Select shape | `"TYPE"` | String | - | Required |

### First (`TYPE = "FIRST"`)

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 2 | First-only value | `"FIRST_VALUE"` | Number | - | Required |

### Second (`TYPE = "SECOND"`)

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 3 | Second-only value | `"SECOND_VALUE"` | String | - | Required |
""",
        encoding="utf-8",
    )

    parsed = ex.parse_chapter(path)[0]
    assert [(variant.field, variant.equals) for variant in parsed.variants] == [
        ("TYPE", "FIRST"),
        ("TYPE", "SECOND"),
    ]
    assert {field.key for field in parsed.tables[0].fields} == {"TYPE"}

    draft = yaml.safe_load(ex.render_draft(parsed))
    assert "unmergedTables" not in draft["extraction"]
    assert draft["variants"][0]["when"] == [{"path": "TYPE", "equals": "FIRST"}]
    assert draft["variants"][1]["fields"][0]["key"] == "SECOND_VALUE"


def test_bold_table_labels_supply_literal_variant_selectors(tmp_path: Path):
    """A bold label immediately preceding a table is equivalent to a heading."""

    path = tmp_path / "99_DB_BoldVariant.md"
    path.write_text(
        """## 1. `/db/BOLD-VARIANT` -- bold variant labels

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Type | `TYPE` | String | - | Required |

**Constant (`TYPE="CONST"`) additional parameters**

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 2 | Constant value | `CONST_VALUE` | Number | - | Required |

**User (`TYPE="USER"`) additional parameters**

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 3 | User value | `USER_VALUE` | Number | - | Required |
""",
        encoding="utf-8",
    )

    parsed = ex.parse_chapter(path)[0]
    assert [(variant.field, variant.equals) for variant in parsed.variants] == [
        ("TYPE", "CONST"),
        ("TYPE", "USER"),
    ]


def test_bold_table_label_survives_an_advisory_before_its_table(tmp_path: Path):
    """A note between a bold selector label and table must not reuse the prior label."""
    path = tmp_path / "99_DB_AdvisoryVariant.md"
    path.write_text(
        """## 1. `/db/ADVISORY-VARIANT` -- advisory variant

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Shape | `SHAPE` | String | - | Required |

**Round (`SHAPE="ROUND"`)**

> The manual explains this value before listing its fields.

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 2 | Radius | `RADIUS` | Number | - | Required |
""",
        encoding="utf-8",
    )

    parsed = ex.parse_chapter(path)[0]
    assert [(variant.field, variant.equals) for variant in parsed.variants] == [("SHAPE", "ROUND")]


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        pytest.param('SHAPE = "ELEMENT" 추가 파라미터', (("SHAPE", ("ELEMENT",)),), id="quoted_string_equals"),
        pytest.param('SECT (`"SECTTYPE": "DBUSER"`)', (("SECTTYPE", ("DBUSER",)),), id="backticked_quoted_key_colon"),
        pytest.param("Truss (STYPE: 1)", (("STYPE", (1,)),), id="colon_numeric"),
        pytest.param("Vehicle K/Military(LOAD_MODEL=2/3)", (("LOAD_MODEL", (2, 3)),), id="slash_numeric_list"),
        pytest.param('Profile (INPUT=2D, CURVE="SPLINE")', (("INPUT", ("2D",)), ("CURVE", ("SPLINE",))), id="two_explicit_gates"),
        pytest.param("M&S (DAMPING_METHOD=1)", (("DAMPING_METHOD", (1,)),), id="numeric_equals"),
    ],
)
def test_variant_conditions_transcribe_manual_heading_forms(heading: str, expected: tuple[tuple[str, tuple], ...]):
    assert ex._variant_conditions(heading) == expected


def test_explicit_variants_keep_unlabelled_supplementary_tables_unmerged(tmp_path: Path):
    """An explicit table can merge without guessing a label-only neighbour."""
    path = tmp_path / "99_DB_PartialVariants.md"
    path.write_text(
        """## 1. `/db/PARTIAL-VARIANT` -- partial variants

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Type | `TYPE` | String | - | Required |

### First (`TYPE="FIRST"`)
| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 2 | First value | `FIRST_VALUE` | Number | - | Required |

### A label without a wire value
| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 3 | Unknown value | `UNKNOWN_VALUE` | Number | - | Required |
""",
        encoding="utf-8",
    )

    parsed = ex.parse_chapter(path)[0]
    draft = yaml.safe_load(ex.render_draft(parsed))
    assert [(variant.field, variant.equals) for variant in parsed.variants] == [("TYPE", "FIRST")]
    assert draft["variants"][0]["when"] == [{"path": "TYPE", "equals": "FIRST"}]
    assert draft["extraction"]["unmergedTables"] == [
        {
            "heading": "A label without a wire value",
            "fields": 1,
            "line": 12,
            # The count says a gap exists; the names say what is in it, which
            # is what lets validate_contracts.py waive per name instead of
            # skipping the contract. See MD-48.
            "fieldNames": ["UNKNOWN_VALUE"],
        }
    ]


def test_a_key_range_row_names_every_key_the_schema_lists_between_its_ends(tmp_path: Path):
    """`"W_R" ~ "HE_B"` is an interval, and the schema says what is inside it.

    `/db/CO_S` compressed nine RGB components into one row and the parser read
    the two ends as two parallel keys, dropping the seven between them from
    both SDKs' payloads. The row's No. span says how many there are and the
    section's JSON Schema says which, so all three have to agree.
    """

    path = tmp_path / "99_DB_Range.md"
    path.write_text(
        """## 1. `/db/RANGE-ROW` -- range row

### JSON Schema

```json
{
  "RANGE-ROW": {
    "type": "object",
    "properties": {
      "W_R": { "description": "Red",   "type": "integer" },
      "W_G": { "description": "Green", "type": "integer" },
      "W_B": { "description": "Blue",  "type": "integer" },
      "FACT": { "description": "Opacity", "type": "number" }
    }
  }
}
```

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1-3 | RGB | `"W_R"` ~ `"W_B"` | Integer | - | Optional |
| 4 | Opacity | `"FACT"` | Number | - | Optional |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    assert [field.key for field in section.tables[0].fields] == ["W_R", "W_G", "W_B", "FACT"]


def test_a_key_range_row_stays_unexpanded_when_the_count_disagrees(tmp_path: Path):
    """Two statements agreeing is the evidence; one of them alone is not."""

    path = tmp_path / "99_DB_RangeMismatch.md"
    path.write_text(
        """## 1. `/db/RANGE-MISMATCH` -- range row whose span is wrong

### JSON Schema

```json
{
  "RANGE-MISMATCH": {
    "type": "object",
    "properties": {
      "W_R": { "description": "Red",   "type": "integer" },
      "W_G": { "description": "Green", "type": "integer" },
      "W_B": { "description": "Blue",  "type": "integer" }
    }
  }
}
```

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1-7 | RGB | `"W_R"` ~ `"W_B"` | Integer | - | Optional |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    keys = [field.key for field in section.tables[0].fields]
    assert keys == ['W_R" ~ "W_B']
    assert any("is not a single field name" in note for note in section.tables[0].fields[0].notes)


def test_an_enum_the_manual_calls_a_sample_is_not_transcribed(tmp_path: Path):
    """A list the manual's own description outsizes is illustrative.

    `/DESIGN/RC/KDS-41-20-2022/DCRM-BEAM` describes `MAIN_REBAR` as
    "19종 (D4 ~ D57)" and its schema lists five values; adopting them published
    a union that made every bar size from D10 up untypeable.
    """

    path = tmp_path / "99_DB_SampledEnum.md"
    path.write_text(
        """## 1. `/db/SAMPLED-ENUM` -- sampled enum

### JSON Schema

```json
{
  "SAMPLED-ENUM": {
    "type": "object",
    "properties": {
      "SIZE":  { "description": "Bar size", "type": "string", "enum": ["D4", "D5"] },
      "GRADE": { "description": "Grade",    "type": "string", "enum": ["A", "B"] }
    }
  }
}
```

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Bar size · 19종 (D4 ~ D57) | `"SIZE"` | String (enum) | - | Required |
| 2 | Grade | `"GRADE"` | String (enum) | - | Required |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    by_key = {field.key: field for field in section.tables[0].fields}
    assert by_key["SIZE"].enum is None
    assert any("is a sample" in note for note in by_key["SIZE"].notes)
    # A list nothing contradicts is still transcribed.
    assert by_key["GRADE"].enum == ["A", "B"]


def test_a_schema_root_the_table_never_names_is_reported(tmp_path: Path):
    """The table is the lossy rendering, and silence about that shipped once.

    `/db/FIMP`'s schema names `CONC` and `STEEL`, its Specifications table
    names neither, and the contract drafted from the table alone declared a
    three-level object as ten flat top-level fields.
    """

    path = tmp_path / "99_DB_SchemaOnlyRoot.md"
    path.write_text(
        """## 1. `/db/SCHEMA-ONLY-ROOT` -- a root only the schema names

### JSON Schema

```json
{
  "SCHEMA-ONLY-ROOT": {
    "type": "object",
    "properties": {
      "NAME": { "description": "Name", "type": "string" },
      "CONC": { "description": "Concrete model", "type": "object" }
    }
  }
}
```

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Name | `"NAME"` | String | - | Required |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    assert section.schema_only_roots == ("CONC",)
    assert "own JSON Schema declares CONC" in ex.render_draft(section)


def test_a_tree_marker_nests_as_deep_as_it_repeats(tmp_path: Path):
    """`└ └ LEAF` is two levels down, not one.

    The marker was stripped as a set, so every level collapsed onto the first
    and the rest of the row became an unparseable key.
    """

    path = tmp_path / "99_DB_DeepTree.md"
    path.write_text(
        """## 1. `/db/DEEP-TREE` -- nested tree markers

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Parent | `"PARENT"` | Object | - | Required |
| 2 | Child | `└ CHILD` | Object | - | Required |
| 3 | Leaf | `└ └ LEAF` | String | - | Required |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    parent = section.tables[0].fields[0]
    assert parent.key == "PARENT"
    assert [child.key for child in parent.properties] == ["CHILD"]
    assert [leaf.key for leaf in parent.properties[0].properties] == ["LEAF"]


def test_a_repeated_key_under_a_different_tree_parent_is_not_a_duplicate(tmp_path: Path):
    """`NAME` under LAYER1 and `NAME` under LAYER2 are two fields.

    Duplicate suppression scopes a repeated key by the No. column's parent,
    because `CONCRETE.CODE` and `REBAR.CODE` share a last token and are not
    the same field. A table that nests with `└` markers has no numbered scope,
    so the check collapsed to the bare key and dropped every repeat anywhere
    in the table.

    A rebar table is nothing but repeats.
    `/DESIGN/SRC/AIK-SRC2K/MRBD` kept 14 of the 54 paths its own JSON Schema
    declares - 53 rows across that chapter, and none anywhere else - which is
    what held it out of the source of truth. The running tree path is the
    scope those rows do have.
    """

    path = tmp_path / "99_DESIGN_TreeRepeat.md"
    path.write_text(
        """## 1. `/DESIGN/TREE-REPEAT` -- repeated keys under tree markers

| Key | Value Type | Description | Default | Required |
|---|---|---|---|---|
| `SECTOR_I` | Object | I-end rebar. | | |
| └ `TOP` | Object | Top rebar. | | O |
| └ └ `LAYER1` | Object | First layer. | | O |
| └ └ └ `NAME` | String | Size. | | O |
| └ └ └ `NUM` | Integer | Count. | | O |
| └ └ `LAYER2` | Object | Second layer. | | |
| └ └ └ `NAME` | String | Size. | | O |
| └ └ └ `NUM` | Integer | Count. | | O |
| `SECTOR_J` | Object | J-end rebar. | | |
| └ `TOP` | Object | Top rebar. | | O |
| └ └ `LAYER1` | Object | First layer. | | O |
| └ └ └ `NAME` | String | Size. | | O |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    roots = {field.key: field for field in section.tables[0].fields}
    assert list(roots) == ["SECTOR_I", "SECTOR_J"]

    top = roots["SECTOR_I"].properties[0]
    assert [layer.key for layer in top.properties] == ["LAYER1", "LAYER2"]
    # The second layer keeps its own NAME and NUM rather than losing them to
    # the first layer's.
    for layer in top.properties:
        assert [leaf.key for leaf in layer.properties] == ["NAME", "NUM"]

    # And a whole second sector repeating the same subtree survives too, which
    # needs the root row itself to be part of the scope.
    assert roots["SECTOR_J"].properties[0].properties[0].properties[0].key == "NAME"


def test_a_table_without_tree_markers_keeps_its_numbered_duplicate_scope(tmp_path: Path):
    """The tree scope must not loosen the check it sits beside.

    Two rows numbered into the same object are still one field listed twice,
    and a table with no markers never enters the tree path at all.
    """

    path = tmp_path / "99_DB_NumberedDuplicate.md"
    path.write_text(
        """## 1. `/db/NUMBERED-DUP` -- a key listed twice in one scope

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Parent | `"PARENT"` | Object | - | Required |
| (1) | Child | `"CHILD"` | String | - | Required |
| (1) | Child again | `"CHILD"` | String | - | Required |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    parent = section.tables[0].fields[0]
    assert [child.key for child in parent.properties] == ["CHILD"]


def test_a_parenthesised_child_repeating_an_earlier_top_level_key_is_kept(tmp_path: Path):
    """A `(1)` row's scope is the plain-numbered row above it, not the table.

    `_number_parent` reads dotted and dashed numbers only, so a `(1)` row used
    to share one scope with the top level: a nested key that repeated any
    earlier field's name was taken for a duplicate and dropped without a
    trace. /db/EFCT is the shape - a root `LCNAME` two rows above hid
    `COMB_LIST[].LCNAME` - and 27 documented members across eight contracts
    were lost that way until 2026-09-21.
    """

    path = tmp_path / "99_DB_ParenChild.md"
    path.write_text(
        """## 1. `/db/PAREN-CHILD` -- a nested key repeating a root key

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Load Case Name | `"LCNAME"` | String | - | Required |
| 2 | Cases | `"COMB_LIST"` | Array [Object] | - | Required |
| (1) | Load Case Name | `"LCNAME"` | String | - | Required |
| (2) | Scale Factor | `"FACTOR"` | Number | - | Required |
| 3 | Other cases | `"OTHER_LIST"` | Array [Object] | - | Optional |
| (1) | Load Case Name | `"LCNAME"` | String | - | Required |
""",
        encoding="utf-8",
    )

    fields = ex.parse_chapter(path)[0].tables[0].fields
    by_key = {field.key: field for field in fields}
    assert [child.key for child in by_key["COMB_LIST"].properties] == ["LCNAME", "FACTOR"]
    assert [child.key for child in by_key["OTHER_LIST"].properties] == ["LCNAME"]


def test_a_row_required_only_in_its_own_mode_is_conditional(tmp_path: Path):
    """A mode or group column scopes each row's "Required" to that group.

    /view/ACTIVE's N_LIST is required in "Active" mode and absent from "All";
    read flat it was required everywhere. A key every group lists stays
    required, and a child row's blank group cell belongs to its parent.
    """

    path = tmp_path / "99_VIEW_Modes.md"
    path.write_text(
        """## 1. `/view/MODES` -- rows sorted by mode

| No. | 모드 | 설명 | Key | Value 타입 | 필수 |
|---|---|---|---|---|---|
| 1 | All | Mode | `"MODE"` | String | **Required** |
| 1 | Active | Mode | `"MODE"` | String | **Required** |
| 2 | Active | Nodes | `"N_LIST"` | Array [Integer] | **Required** |
| 3 | Active | Colour | `"COLOR"` | Object | **Required** |
| 3-1 | | Red | `COLOR.R` | Integer | **Required** |
""",
        encoding="utf-8",
    )

    fields = {field.key: field for field in ex.parse_chapter(path)[0].tables[0].fields}
    assert fields["MODE"].requirement == "required"
    assert fields["N_LIST"].requirement == "conditional"
    assert fields["N_LIST"].condition == "모드: Active"


def test_a_repeated_heading_selector_is_not_a_discriminator(tmp_path: Path):
    """One value cannot select two field sets, so neither table merges.

    ``/db/ELEM`` heads five tables ``STYPE: 1`` to ``STYPE: 3`` across four
    element types, so ``STYPE: 1`` heads both a tension-only and a
    compression-only truss. The pair with ``TYPE`` is the real gate and the
    headings name only half of it, so every table on the repeated field stays
    unmerged rather than becoming a variant that claims a value twice.
    """

    path = tmp_path / "99_DB_HalfNamedGate.md"
    path.write_text(
        """## 1. `/db/HALF-GATE` -- half-named gate

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Subtype | `STYPE` | Integer | - | Required |
| 2 | Input dimension | `INPUT` | String | - | Required |

### Tension only -- Truss (STYPE: 1)
| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 2 | Allowable compression | `TENS` | Number | - | Required |

### Compression only -- Truss (STYPE: 1)
| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 3 | Allowable tension | `TENS_C` | Number | - | Required |

### Cable (STYPE: 3)
| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 4 | Cable option | `CABLE` | Integer | - | Required |

### An independent gate (`INPUT="2D"`)
| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 5 | Plan value | `PLAN` | Number | - | Required |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    draft = yaml.safe_load(ex.render_draft(section))

    # STYPE: 3 is unique but shares the field that repeated, so it goes too -
    # a contract naming one STYPE branch and hiding two reads as complete.
    assert [variant["when"] for variant in draft["variants"]] == [
        [{"path": "INPUT", "equals": "2D"}]
    ]
    assert [table["heading"] for table in draft["extraction"]["unmergedTables"]] == [
        "Tension only -- Truss (STYPE: 1)",
        "Compression only -- Truss (STYPE: 1)",
        "Cable (STYPE: 3)",
    ]


def test_manual_check_compares_repeated_literal_variants_in_source_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Two manual tables sharing one selector round-trip as unmerged tables."""
    path = tmp_path / "99_DB_RepeatedVariant.md"
    path.write_text(
        """## 1. `/db/REPEATED-VARIANT` -- repeated variant

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Type | `TYPE` | String | - | Required |

### First group (`TYPE="A"`)
| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 2 | First value | `FIRST_VALUE` | Number | - | Required |

### Second group (`TYPE="A"`)
| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 3 | Second value | `SECOND_VALUE` | Number | - | Required |
""",
        encoding="utf-8",
    )
    section = ex.parse_chapter(path)[0]
    contract = yaml.safe_load(ex.render_draft(section))
    contract.pop("draft")
    endpoint_dir = tmp_path / "endpoints"
    endpoint_dir.mkdir()
    (endpoint_dir / "db-repeated-variant.yaml").write_text(yaml.safe_dump(contract), encoding="utf-8")
    monkeypatch.setattr(ex, "ENDPOINT_DIR", endpoint_dir)

    assert ex.run_check([section]) == 0


def test_prose_and_inline_bold_emphasis_do_not_replace_a_table_heading(tmp_path: Path):
    """Only a full bold label directly attached to a table becomes its heading."""

    path = tmp_path / "99_DB_ProseBeforeTable.md"
    path.write_text(
        """## 1. `/db/PROSE-LABEL` -- prose before a table

### Parameters

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Root | `ROOT` | String | - | Required |

The following has the same child structure (all **Required**):

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 2 | Child | `CHILD` | String | - | Required |
""",
        encoding="utf-8",
    )

    tables = ex.parse_chapter(path)[0].tables
    assert [table.heading for table in tables] == ["Parameters", "Parameters"]


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        pytest.param('Variant (`TYPE="A"` / `TYPE="B"`)', "selector with several values", id="repeated_string_assignments"),
        pytest.param("Variant (`FLOOR_DIST_TYPE=1 or 2`)", "selector with several values", id="numeric_or_list"),
        pytest.param('Variant (`TYPE="A"`)', "selector with one value", id="one_string_value"),
        pytest.param("Variant (STYPE: 1)", "selector with one value", id="colon_numeric_value"),
        pytest.param("Variant (`TYPE`)", "no selector stated", id="field_name_without_equality"),
        pytest.param("Variant table", "no selector stated", id="label_only"),
    ],
)
def test_selector_evidence_reports_only_explicit_manual_literals(heading: str, expected: str):
    assert ex._selector_evidence(heading) == expected


def test_inline_boolean_variant_rows_preserve_branches_and_roman_children(tmp_path: Path):
    """A divider row in one table is a variant only when it names a wire value."""
    path = tmp_path / "99_DB_InlineVariants.md"
    path.write_text(
        """# 99 DB Inline variants

## 1. `/db/INLINE-VARIANT` -- Inline variants

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Choose mode | `"OPT_MODE"` | Boolean | false | Optional |
| | General (`OPT_MODE`=false) | | | | |
| 2 | Items | `"ITEMS"` | Array[Object] | - | Required |
| (i) | General value | `"VALUE"` | Number | - | Required |
| | Optimized (`OPT_MODE`=true) | | | | |
| 2 | Distance | `"DISTANCE"` | Number | - | Required |
""",
        encoding="utf-8",
    )

    parsed = ex.parse_chapter(path)[0]
    assert [(variant.field, variant.equals) for variant in parsed.variants] == [
        ("OPT_MODE", False),
        ("OPT_MODE", True),
    ]
    assert [field.key for field in parsed.tables[0].fields] == ["OPT_MODE"]
    items = parsed.variants[0].table.fields[0]
    assert items.key == "ITEMS"
    assert items.properties[0].key == "VALUE"

    draft = yaml.safe_load(ex.render_draft(parsed))
    assert draft["variants"][0]["when"] == [{"path": "OPT_MODE", "equals": False}]


def test_manual_check_compares_explicit_variant_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "99_DB_VariantCheck.md"
    path.write_text(
        """# 99 DB — Variant check

## 1. `/db/VARIANT-CHECK` — Explicit variants

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Select shape | `"TYPE"` | String | - | Required |

### First (`TYPE = "FIRST"`)

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 2 | First-only value | `"FIRST_VALUE"` | Number | 1 | Required |
""",
        encoding="utf-8",
    )
    parsed = ex.parse_chapter(path)[0]
    contract = yaml.safe_load(ex.render_draft(parsed))
    contract.pop("draft")
    endpoint_dir = tmp_path / "endpoints"
    endpoint_dir.mkdir()
    (endpoint_dir / "db-variant-check.yaml").write_text(yaml.safe_dump(contract), encoding="utf-8")
    monkeypatch.setattr(ex, "ENDPOINT_DIR", endpoint_dir)

    assert ex.run_check([parsed]) == 0
    contract["variants"][0]["fields"][0]["documentedDefault"] = 0
    (endpoint_dir / "db-variant-check.yaml").write_text(yaml.safe_dump(contract), encoding="utf-8")
    assert ex.run_check([parsed]) == 1


def test_draft_never_answers_safe_to_omit_from_the_manual(section: ex.Section):
    """The manual's "Optional" must never become a claim about the product.

    Without live evidence every field stays `unverified`, including the four the
    synthetic chapter marks Optional.
    """
    draft = yaml.safe_load(ex.render_draft(section))

    def walk(fields):
        for field in fields:
            assert field["safeToOmit"] == "unverified", field["key"]
            assert "omissionEvidence" not in field
            walk(field.get("properties", []))

    walk(draft["fields"])
    assert draft["verification"]["status"] == "manual_only"
    assert all(f["provenance"] == "manual" for f in draft["fields"])


def test_draft_answers_safe_to_omit_only_from_a_confirmed_live_payload(section: ex.Section):
    evidence = ex.LiveOmission(
        case="Synthetic",
        endpoint="/db/SYNTH",
        sent=frozenset({"NAME", "ITEMS"}),
        products="gen and civil",
    )
    fields = {f["key"]: f for f in yaml.safe_load(ex.render_draft(section, evidence))["fields"]}

    # Sent in the payload that passed: nothing was learned about omitting them.
    assert fields["NAME"]["safeToOmit"] == "unverified"
    assert fields["ITEMS"]["safeToOmit"] == "unverified"

    # Absent from a payload a product accepted: that is evidence, and it is cited.
    assert fields["bFLAG"]["safeToOmit"] is True
    assert "Synthetic" in fields["bFLAG"]["omissionEvidence"]
    assert "not that the resulting model" in fields["bFLAG"]["omissionEvidence"]


def test_a_case_that_sends_no_create_payload_is_not_omission_evidence():
    """An empty create payload is a skipped request, not an accepted one.

    `live_crud_check.py` writes `{}` for records the product creates itself -
    UNIT, STYP, STYP-M1 and the four CO_* colour defaults, all GET/PUT-only.
    Its POST leg never runs there. Reading that as "the product accepted every
    field's absence" turned a request nobody made into blanket proof: it marked
    31 fields across four promoted contracts safeToOmit on no evidence at all.
    That is the /db/NMAS shape exactly - the field the manual calls Optional
    and the server dies without.
    """
    evidence = ex.live_omission_evidence()

    assert evidence, "the checker should still yield evidence for ordinary cases"
    for endpoint, omission in evidence.items():
        assert omission.sent, f"{endpoint} claims evidence from an empty payload"


def test_an_empty_live_payload_proves_nothing_about_omission(section: ex.Section):
    """Belt and braces: even handed one directly, a draft must not believe it."""
    evidence = ex.LiveOmission(
        case="Singleton", endpoint="/db/SYNTH", sent=frozenset(), products="civil"
    )
    fields = {f["key"]: f for f in yaml.safe_load(ex.render_draft(section, evidence))["fields"]}

    for key, field in fields.items():
        assert field["safeToOmit"] == "unverified", key


def test_nested_fields_are_never_given_live_evidence(section: ex.Section):
    """A top-level payload key says nothing about members inside it."""
    evidence = ex.LiveOmission(
        case="Synthetic", endpoint="/db/SYNTH", sent=frozenset({"NAME"}), products="gen"
    )
    fields = {f["key"]: f for f in yaml.safe_load(ex.render_draft(section, evidence))["fields"]}

    for child in fields["ITEMS"]["properties"]:
        assert child["safeToOmit"] == "unverified", child["key"]


@pytest.mark.parametrize(
    ("payload", "field_products", "evidence_products", "expected"),
    [
        pytest.param({"MODE": "OFF"}, (), frozenset({"gen", "civil"}), "unverified",
                     id="different-conditional-branch-is-not-omission-evidence"),
        pytest.param({"MODE": "ON"}, (), frozenset({"gen", "civil"}), True,
                     id="matching-conditional-branch-is-omission-evidence"),
        pytest.param({"MODE": "ON"}, ("gen",), frozenset({"civil"}), "unverified",
                     id="different-product-is-not-omission-evidence"),
    ],
)
def test_live_omission_evidence_matches_the_exercised_branch_and_product(
    payload, field_products, evidence_products, expected,
):
    fields = [
        ex.ParsedField(
            key="MODE", description="selector", type="string", items=None,
            requirement="required", documented_default=None,
        ),
        ex.ParsedField(
            key="VALUE", description="branch value", type="number", items=None,
            requirement="conditional", documented_default=None,
            applies_when=[("MODE", ("ON",))], products=field_products,
        ),
    ]
    evidence = ex.LiveOmission(
        case="Synthetic", endpoint="/db/SYNTH", sent=frozenset(payload),
        products="test products", payload=payload, product_names=evidence_products,
    )
    rendered = yaml.safe_load("fields:\n" + "\n".join(ex._render_fields(fields, "  ", evidence)))

    assert rendered["fields"][1]["safeToOmit"] == expected


def test_draft_is_valid_yaml_but_cannot_validate_as_a_contract(section: ex.Section):
    """A draft must be unusable until read, and unusable for one obvious reason."""
    jsonschema = pytest.importorskip("jsonschema")
    import json

    schema = json.loads(
        (ROOT / "contracts" / "schema" / "endpoint-contract.schema.json").read_text(encoding="utf-8")
    )
    draft = yaml.safe_load(ex.render_draft(section))
    assert draft["draft"] is True

    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(draft))
    assert errors, "a draft must not validate; review is what promotes it"
    # `draft` is the deliberate gate. This synthetic table also carries an
    # intentionally ambiguous multi-key row, which is now independently
    # rejected by the wire-key schema rather than being allowed into a contract.
    assert ("draft",) in {tuple(e.path) for e in errors}, [
        (list(e.path), e.message) for e in errors
    ]


def test_claiming_safe_to_omit_requires_evidence():
    """`safeToOmit: true` without omissionEvidence is exactly the mistake to block."""
    jsonschema = pytest.importorskip("jsonschema")
    import json

    schema = json.loads(
        (ROOT / "contracts" / "schema" / "endpoint-contract.schema.json").read_text(encoding="utf-8")
    )
    field = {
        "key": "X",
        "type": "number",
        "requirement": "optional",
        "documentedOptional": True,
        "safeToOmit": True,
        "provenance": "manual",
    }
    validator = jsonschema.Draft202012Validator(schema["$defs"]["field"])

    assert [e.message for e in validator.iter_errors(field)] == [
        "'omissionEvidence' is a required property"
    ]

    field["omissionEvidence"] = "live_crud_check.py's Node case omitted it and passed"
    assert not list(validator.iter_errors(field))


def test_documented_default_note_requires_a_null_literal_default():
    """Manual prose must never be mistaken for a literal wire default."""
    jsonschema = pytest.importorskip("jsonschema")
    import json

    schema = json.loads(
        (ROOT / "contracts" / "schema" / "endpoint-contract.schema.json").read_text(encoding="utf-8")
    )
    field = {
        "key": "MODE",
        "type": "string",
        "requirement": "optional",
        "documentedDefault": "AUTO",
        "documentedDefaultNote": "Auto",
        "documentedOptional": True,
        "safeToOmit": "unverified",
        "provenance": "manual",
    }
    validator = jsonschema.Draft202012Validator(schema["$defs"]["field"])

    assert any("None was expected" in error.message for error in validator.iter_errors(field))

    field["documentedDefault"] = None
    assert not list(validator.iter_errors(field))


@pytest.mark.parametrize(
    ("value_type", "required", "expected_type", "expected_requirement"),
    [
        pytest.param(
            "",
            "Optional",
            "unstated",
            "optional",
            id="blank_value_type_becomes_unstated_without_inventing_string",
        ),
        pytest.param(
            "Number",
            "",
            "number",
            "unstated",
            id="blank_requiredness_becomes_unstated_without_inventing_optional",
        ),
    ],
)
def test_unstated_manual_columns_render_as_explicit_unknown_claims(
    value_type: str,
    required: str,
    expected_type: str,
    expected_requirement: str,
    tmp_path: Path,
):
    path = tmp_path / "99_DB_UnstatedColumns.md"
    path.write_text(
        "## 1. `/db/UNSTATED` -- Unstated columns\n\n"
        "| No. | Description | Key | Value Type | Default | Required |\n"
        "|-----|-------------|-----|------------|---------|----------|\n"
        f"| 1 | Field | `FIELD` | {value_type} | - | {required} |\n",
        encoding="utf-8",
    )

    draft = yaml.safe_load(ex.render_draft(ex.parse_chapter(path)[0]))
    field = draft["fields"][0]
    assert field["type"] == expected_type
    assert field["requirement"] == expected_requirement
    assert field["documentedOptional"] is (True if expected_requirement == "optional" else None)


@pytest.mark.parametrize(
    ("cell", "requirement", "condition"),
    [
        pytest.param("GET only", "read_only", None, id="get_only_is_read_only"),
        pytest.param(
            "SRC: \ud544\uc218 / CONCRETE\u00b7STEEL: \uc120\ud0dd",
            "conditional",
            "SRC: \ud544\uc218 / CONCRETE\u00b7STEEL: \uc120\ud0dd",
            id="source_specific_requiredness_preserves_manual_condition",
        ),
    ],
)
def test_documented_requiredness_forms_are_not_downgraded_to_unstated(
    cell: str, requirement: str, condition: str | None
):
    actual_requirement, actual_condition, note = ex._normalize_requirement(cell)
    assert (actual_requirement, actual_condition, note) == (requirement, condition, None)


def test_report_counts_manual_columns_preserved_as_unstated(capsys: pytest.CaptureFixture[str]):
    ex.run_report(
        [
            ex.Section(
                "99_DB_Unstated.md",
                "1",
                endpoint="/db/UNSTATED",
                title="Unstated",
                heading="Unstated",
                lines=[],
                methods={"GET"},
                tables=[
                    ex.ParsedTable(
                        heading="Parameters",
                        line=1,
                        fields=[
                            ex.ParsedField("TYPE", "", None, None, "optional", None),
                            ex.ParsedField("REQUIRED", "", "string", None, None, None),
                        ],
                    )
                ],
            )
        ],
        {},
    )

    assert "1 requiredness value(s), 1 Value Type value(s)" in capsys.readouterr().out


def test_documented_optional_null_requires_unstated_requiredness():
    """Null has one precise meaning, not a loophole for optional fields."""
    jsonschema = pytest.importorskip("jsonschema")
    import json

    schema = json.loads(
        (ROOT / "contracts" / "schema" / "endpoint-contract.schema.json").read_text(encoding="utf-8")
    )
    field = {
        "key": "MODE",
        "type": "unstated",
        "requirement": "optional",
        "documentedDefault": None,
        "documentedOptional": None,
        "safeToOmit": "unverified",
        "provenance": "manual",
    }
    validator = jsonschema.Draft202012Validator(schema["$defs"]["field"])

    assert any("'unstated' was expected" in error.message for error in validator.iter_errors(field))

    field["requirement"] = "unstated"
    assert not list(validator.iter_errors(field))


def test_field_names_that_yaml_would_mangle_are_quoted(section: ex.Section):
    """`NO` is a real MIDAS field name and a YAML 1.1 boolean."""
    draft = yaml.safe_load(ex.render_draft(section))

    assert draft["fields"][0]["key"] == "NO"


def test_check_reports_drift_between_a_contract_and_the_manual(section: ex.Section):
    manual = ex._flatten_manual(section.tables[0].fields)

    assert manual["ITEMS.ITEM_NAME"].requirement == "required"
    assert set(manual) >= {"NAME", "ITEMS", "ITEMS.ITEM_NAME", "CFG.MODE"}


def test_manual_enum_comparison_uses_array_item_values_when_applicable(tmp_path: Path):
    """A field enum and an array-item enum are intentionally different slots."""
    path = tmp_path / "99_DB_ArrayEnum.md"
    path.write_text(
        """# 99 DB — Array enum

## 1. `/db/ARRAY-ENUM` — Array enum

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Modes | `"MODES"` | Array [String (enum)] | - | Required |

**`MODES` values (enum):**

| Value | Description |
|-------|-------------|
| `"A"` | A |
| `"B"` | B |
""",
        encoding="utf-8",
    )
    field = ex.parse_chapter(path)[0].tables[0].fields[0]
    assert field.type == "array"
    assert field.enum == ["A", "B"]
    assert yaml.safe_load(ex.render_draft(ex.parse_chapter(path)[0]))["fields"][0]["items"]["enum"] == [
        "A",
        "B",
    ]


METHOD_DECLARATION_FORMS = {
    "colon inside the bold": "- **Methods**: `POST`, `GET`",
    "colon outside the bold": "**Active Methods:** `POST, GET`",
    "middle-dot separator": "**Methods:** `POST` · `GET`",
    "two-column table row": "| **Method** | `POST`, `GET` |",
    "heading, verbs below": "### Active Methods\n\n`POST` · `GET`",
    "heading, verbs in a table": (
        "### HTTP Methods\n\n"
        "| Method | URL | 설명 |\n"
        "|--------|-----|------|\n"
        "| POST | `{base_url}/db/SYNTH` | create |\n"
        "| GET | `{base_url}/db/SYNTH` | read |"
    ),
    "numbered local HTTP heading, verbs in a table": (
        "### 1-1. HTTP 메서드 및 URL\n\n"
        "| 메서드 | URL | 설명 |\n"
        "|--------|-----|------|\n"
        "| POST | `{base_url}/db/SYNTH` | create |\n"
        "| GET | `{base_url}/db/SYNTH` | read |"
    ),
}


@pytest.mark.parametrize("form", sorted(METHOD_DECLARATION_FORMS))
def test_every_declaration_form_the_chapters_use_is_read(form: str, tmp_path: Path):
    """The chapters state their verbs six ways, and a missed form is not cosmetic.

    A section whose verbs go unread falls back to the /db/* default of all four -
    which is how /db/GRUP's first draft claimed a DELETE the endpoint does not
    serve - or, once that fallback became a refusal, blocks promotion outright.
    Reading only the narrowest form made 276 of 386 sections look like the manual
    never stated its methods; the real number is 26.
    """
    path = tmp_path / "99_DB_Forms.md"
    path.write_text(
        "# 99 DB — Forms\n\n## 1. `/db/SYNTH` — Synthetic\n\n"
        + METHOD_DECLARATION_FORMS[form]
        + "\n",
        encoding="utf-8",
    )
    assert ex.parse_chapter(path)[0].methods == ["GET", "POST"]


def test_a_section_that_states_no_methods_stays_empty(tmp_path: Path):
    """The fallback belongs to the caller, so silence must stay legible here."""
    path = tmp_path / "99_DB_Silent.md"
    path.write_text("# 99 DB — Silent\n\n## 1. `/db/SYNTH` — Synthetic\n\nNo verbs anywhere.\n", encoding="utf-8")
    assert ex.parse_chapter(path)[0].methods == []


def test_a_comparison_table_is_not_a_method_declaration(tmp_path: Path):
    """A chapter's trailing summary lands inside the last endpoint's section.

    Only a heading that names an endpoint starts a new section, so a closing
    "비교 요약" belongs to whichever endpoint came last. 14_DB_Pushover.md ends
    with exactly this three-column comparison, and reading its first value
    column handed /db/POLC-M1 the *general* endpoint's POST - a verb that same
    chapter twice says Hyper-S does not serve.
    """
    path = tmp_path / "99_DB_Compare.md"
    path.write_text(
        """# 99 DB — Compare

## 1. `/db/SYNTH-M1` — Synthetic Hyper-S

### Active Methods

`GET` · `PUT` · `DELETE`

---

## SYNTH vs SYNTH-M1 비교 요약

| 항목 | 일반(General) | Hyper-S(-M1) |
|------|:---:|:---:|
| Active Methods | POST, GET, PUT, DELETE | GET, PUT, DELETE (POST 미지원) |
""",
        encoding="utf-8",
    )
    assert ex.parse_chapter(path)[0].methods == ["DELETE", "GET", "PUT"]


def test_a_normalisation_callout_does_not_restore_the_verb_it_rejects(tmp_path: Path):
    """The manual repo overrules the official docs in `> ⚠️` callouts.

    Such a callout quotes the form it is rejecting in order to reject it, so a
    scan that sweeps verbs out of one reinstates exactly the value the callout
    exists to overrule.
    """
    path = tmp_path / "99_DB_Callout.md"
    path.write_text(
        """# 99 DB — Callout

## 1. `/db/SYNTH-M1` — Synthetic Hyper-S

### Active Methods

`GET` · `PUT` · `DELETE`

> ⚠️ 원문 아티클의 Active Methods 표는 `POST, GET, PUT, DELETE`로 표기돼 있으나,
> 이 챕터는 POST 미지원을 전제한다. 실기 확인 전까지 `GET`/`PUT`/`DELETE`로 유지한다.

### JSON Schema
""",
        encoding="utf-8",
    )
    assert ex.parse_chapter(path)[0].methods == ["DELETE", "GET", "PUT"]


def test_manual_check_compares_declared_methods(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A contract serving a verb the chapter never states is drift.

    Nothing compared the two before, which is how /db/POLC-M1's misread POST
    survived promotion into the contract and from there into both SDKs.
    """
    path = tmp_path / "99_DB_MethodCheck.md"
    path.write_text(
        """# 99 DB — Method check

## 1. `/db/METHOD-CHECK` — Declared methods

- **Methods**: `GET`, `PUT`

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Name | `"NAME"` | String | - | Required |
""",
        encoding="utf-8",
    )
    parsed = ex.parse_chapter(path)[0]
    contract = yaml.safe_load(ex.render_draft(parsed))
    contract.pop("draft")
    endpoint_dir = tmp_path / "endpoints"
    endpoint_dir.mkdir()
    target = endpoint_dir / "db-method-check.yaml"
    target.write_text(yaml.safe_dump(contract), encoding="utf-8")
    monkeypatch.setattr(ex, "ENDPOINT_DIR", endpoint_dir)

    assert ex.run_check([parsed]) == 0

    contract["operations"].append({"method": "POST", "risk": "write"})
    target.write_text(yaml.safe_dump(contract), encoding="utf-8")
    assert ex.run_check([parsed]) == 1

    # A verb the manual denies but a live call proved is a recorded defect, not
    # a silent match - the same escape hatch the field checks already use.
    contract["manualDefects"] = [
        {
            "describes": "method",
            "manualSays": "GET, PUT",
            "actual": "POST is served",
            "evidence": "docs/live_verification_notes.md",
        }
    ]
    target.write_text(yaml.safe_dump(contract), encoding="utf-8")
    assert ex.run_check([parsed]) == 0


def test_a_translated_heading_yields_the_english_label(tmp_path: Path):
    """Chapters 24-27 label sections `English (한글)`; the rest are English.

    Both halves are the manual's, but the label ships as the resource name in
    both packages and `INDEX.md` gives one English name per endpoint, so the
    draft takes the English. A parenthetical with no Hangul is part of the
    label, not a translation of it.
    """
    path = tmp_path / "99_DB_Labels.md"
    path.write_text(
        """# 99 DB — Labels

## 1. `/db/TRANS` — Definition of Frame (프레임 정의)

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Name | `"NAME"` | String | - | Required |

## 2. `/db/PLAIN` — Rebar Input for Checking (Beam/Column)

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Name | `"NAME"` | String | - | Required |
""",
        encoding="utf-8",
    )
    first, second = ex.parse_chapter(path)
    assert yaml.safe_load(ex.render_draft(first))["name"] == "Definition of Frame"
    assert yaml.safe_load(ex.render_draft(second))["name"] == "Rebar Input for Checking (Beam/Column)"


def test_manual_check_compares_the_endpoint_label(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The label is a manual fact, and it ships as the package resource name.

    Nothing compared it: not this check, not validate_contracts.py, and the
    generator's shadow gate reaches only /db/*. So when chapters 24-27 labelled
    their sections in Korean, 113 contracts took a Korean name and /db/DCTL
    carried one into src/midas_nx/ with every gate green - each gate asked
    whether the surfaces agreed, and they did.
    """
    path = tmp_path / "99_DB_LabelCheck.md"
    path.write_text(
        """# 99 DB — Label check

## 1. `/db/LABEL-CHECK` — Definition of Frame (프레임 정의)

- **Methods**: `GET`, `PUT`

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Name | `"NAME"` | String | - | Required |
""",
        encoding="utf-8",
    )
    parsed = ex.parse_chapter(path)[0]
    contract = yaml.safe_load(ex.render_draft(parsed))
    contract.pop("draft")
    endpoint_dir = tmp_path / "endpoints"
    endpoint_dir.mkdir()
    target = endpoint_dir / "db-label-check.yaml"
    target.write_text(yaml.safe_dump(contract), encoding="utf-8")
    monkeypatch.setattr(ex, "ENDPOINT_DIR", endpoint_dir)

    assert ex.run_check([parsed]) == 0

    contract["name"] = "프레임 정의"
    target.write_text(yaml.safe_dump(contract, allow_unicode=True), encoding="utf-8")
    assert ex.run_check([parsed]) == 1


def test_manual_check_compares_the_section_heading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A renumbered chapter leaves every contract below the insert pointing wrong.

    Inserting /db/STYP-M1 at chapter 02's #4 on 2026-08-30 moved eleven
    sections down one, and unifying chapters 24-27's labels rewrote 86 more
    headings. Nothing compared `source.manual.section` against the chapter, so
    103 contracts named a heading that no longer existed - the third blind spot
    of this shape, after the endpoint label and the method set.

    Dash spelling is exempt: 90 contracts write the manual's em dash as `--`,
    and the npm shadow gate already treats that as presentation.
    """
    path = tmp_path / "99_DB_Sections.md"
    path.write_text(
        """# 99 DB — Sections

## 7. `/db/SECTION-CHECK` — Section Check

- **Methods**: `GET`, `PUT`

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Name | `"NAME"` | String | - | Required |
""",
        encoding="utf-8",
    )
    parsed = ex.parse_chapter(path)[0]
    contract = yaml.safe_load(ex.render_draft(parsed))
    contract.pop("draft")
    endpoint_dir = tmp_path / "endpoints"
    endpoint_dir.mkdir()
    target = endpoint_dir / "db-section-check.yaml"
    target.write_text(yaml.safe_dump(contract, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(ex, "ENDPOINT_DIR", endpoint_dir)

    assert ex.run_check([parsed]) == 0

    # The same heading spelled with ASCII dashes stays acceptable.
    contract["source"]["manual"]["section"] = "7. `/db/SECTION-CHECK` -- Section Check"
    target.write_text(yaml.safe_dump(contract, allow_unicode=True), encoding="utf-8")
    assert ex.run_check([parsed]) == 0

    # A stale section number does not.
    contract["source"]["manual"]["section"] = "6. `/db/SECTION-CHECK` — Section Check"
    target.write_text(yaml.safe_dump(contract, allow_unicode=True), encoding="utf-8")
    assert ex.run_check([parsed]) == 1


def test_enum_values_are_read_only_when_the_same_manual_section_states_them(tmp_path: Path):
    """Cover the three enum forms used by the manual, including nested paths."""
    path = tmp_path / "99_DB_Enums.md"
    path.write_text(
        """# 99 DB — Enums

## 1. `/db/ENUM` — Enum forms

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Inline choices | `"INLINE"` | String (enum: `"AUTO"`/`"MANUAL"`) | - | Required |
| 2 | Description choices (`"LEFT"` / `"RIGHT"`) | `"DESCRIBED"` | String (enum) | - | Required |
| 5 | Numeric choices (0=Zero / 1=One / 2=Two) | `"NUMBERED"` | Integer (enum) | - | Required |
| 6 | Symbolic choices (FIRST=First / SECOND=Second) | `"SYMBOLIC"` | String (enum) | - | Required |
| 7 | Reverse symbolic choices (Static: STATIC / Stage: STAGE) | `"REVERSE_SYMBOLIC"` | String (enum) | - | Required |
| 8 | Bare numeric choices (0/1/2) | `"BARE_NUMERIC"` | Integer (enum) | - | Required |
| 3 | Settings | `"SETTINGS"` | Object | - | Required |
| (1) | Table choices | `"KIND"` | String (enum) | - | Required |
| 4 | Item choices | `"ITEMS"` | Array [String (enum)] | - | Required |

**`SETTINGS.KIND` values (enum):**

| Value | Description |
|-------|-------------|
| `"FIRST"` | First |
| `"SECOND"` | Second |

**`ITEMS` values (enum):**

| Value | Description | Value | Description |
|-------|-------------|-------|-------------|
| `"ONE"` | One | `"TWO"` | Two |
""",
        encoding="utf-8",
    )

    parsed = ex.parse_chapter(path)[0]
    fields = {field.key: field for field in parsed.tables[0].fields}
    assert fields["INLINE"].enum == ["AUTO", "MANUAL"]
    assert fields["DESCRIBED"].enum == ["LEFT", "RIGHT"]
    assert fields["NUMBERED"].enum == [0, 1, 2]
    assert fields["SYMBOLIC"].enum == ["FIRST", "SECOND"]
    assert fields["REVERSE_SYMBOLIC"].enum == ["STATIC", "STAGE"]
    assert fields["BARE_NUMERIC"].enum == [0, 1, 2]
    assert fields["SETTINGS"].properties[0].enum == ["FIRST", "SECOND"]
    assert fields["ITEMS"].enum == ["ONE", "TWO"]
    assert not any("values are listed elsewhere" in note for field in ex._walk(parsed.tables[0].fields) for note in field.notes)

    draft = yaml.safe_load(ex.render_draft(parsed))
    draft_fields = {field["key"]: field for field in draft["fields"]}
    assert draft_fields["INLINE"]["enum"] == ["AUTO", "MANUAL"]
    assert draft_fields["SETTINGS"]["properties"][0]["enum"] == ["FIRST", "SECOND"]
    assert draft_fields["ITEMS"]["items"]["enum"] == ["ONE", "TWO"]


def test_markdown_numeric_enum_values_do_not_turn_ranges_or_ellipses_into_enums():
    """Code-spanned alternatives are exact values; abbreviated ranges are not."""
    assert ex._enum_values_from_description("Diagram type: Stress `0` / Force `1`") == [0, 1]
    assert ex._enum_values_from_description("Allowed range `0` ~ `20`") == []
    assert ex._enum_values_from_description("1=Method-1 … 4=Method-4") == []


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        (
            "Material grade · `None`, `SD300`, `SD400`, `SD500`, `SD600`, "
            "`SD700`, `SD400S`, `SD500S`, `SD600S`",
            ["None", "SD300", "SD400", "SD500", "SD600", "SD700", "SD400S", "SD500S", "SD600S"],
        ),
        ("A documented range `D4` ~ `D57` is not an enumerated list", []),
        ("Abbreviated values `ONE`, …, `NINE` are not an enumerated list", []),
    ],
    ids=["comma-separated-code-spans", "range-is-not-enum", "ellipsis-is-not-enum"],
)
def test_description_enum_parser_reads_only_complete_code_span_lists(description: str, expected: list[object]):
    assert ex._enum_values_from_description(description) == expected


def test_same_section_json_schema_fills_only_exact_table_enum_and_array_gaps(tmp_path: Path):
    path = tmp_path / "99_DB_SchemaHints.md"
    path.write_text(
        """## 1. `/db/HINTS` — Schema hints

### JSON Schema

```json
{"type":"object","properties":{"Assign":{"type":"object","required":["MODE","VECTOR"],"properties":{"MODE":{"type":"string","enum":["FIRST","SECOND"]},"VECTOR":{"type":"array","minItems":3,"maxItems":3,"items":{"type":"number"}},"OPTIONAL_NOTE":{"type":"string"}}}}}
```

| No. | Description | Key | Value Type | Default | Required |
|-----|-------------|-----|------------|---------|----------|
| 1 | Mode | `"MODE"` | String (enum) | - | Required |
| 2 | Vector | `"VECTOR"` | Array | - | Required |
| 3 | Optional note | `"OPTIONAL_NOTE"` | String | - | |
""",
        encoding="utf-8",
    )

    fields = {field.key: field for field in ex.parse_chapter(path)[0].tables[0].fields}
    assert fields["MODE"].enum == ["FIRST", "SECOND"]
    assert not fields["MODE"].notes
    assert fields["VECTOR"].items == {"type": "number"}
    assert fields["VECTOR"].constraints == {"minItems": 3, "maxItems": 3}
    assert not fields["VECTOR"].notes
    assert fields["OPTIONAL_NOTE"].requirement == "optional"
    assert not fields["OPTIONAL_NOTE"].notes


def test_same_section_json_schema_supplies_a_missing_default_column_only(tmp_path: Path):
    path = tmp_path / "99_DB_SchemaDefault.md"
    path.write_text(
        """## 1. `/db/DEFAULT` — Schema default

### JSON Schema

```json
{"type":"object","properties":{"Assign":{"type":"object","properties":{"COUNT":{"type":"integer","default":0}}}}}
```

| No. | Description | Key | Value Type | Required |
|-----|-------------|-----|------------|----------|
| 1 | Count | `"COUNT"` | Integer | Optional |
""",
        encoding="utf-8",
    )

    count = ex.parse_chapter(path)[0].tables[0].fields[0]
    assert count.documented_default == 0
    assert not count.notes


def test_missing_default_column_is_recorded_once_in_extraction_not_per_field(tmp_path: Path):
    path = tmp_path / "99_DB_NoDefaultColumn.md"
    path.write_text(
        """## 1. `/db/NO-DEFAULT` -- no Default column

| No. | Description | Key | Value Type | Required |
|---|---|---|---|---|
| 1 | First | `FIRST` | String | Required |
| 2 | Second | `SECOND` | Number | Optional |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    assert all("the table has no Default column" not in field.notes for field in section.tables[0].fields)
    draft = yaml.safe_load(ex.render_draft(section))
    missing = draft["extraction"]["missingColumns"]
    assert len(missing) == 1
    assert missing[0]["columns"] == ["Default"]


@pytest.mark.parametrize(
    ("schema_form", "record_schema"),
    [
        pytest.param(
            "properties_record_wrapper",
            '{"properties":{"Assign":{"type":"object","properties":{"MODE":{"type":"string","enum":["FIRST","SECOND"]}}}}}',
            id="properties_record_wrapper",
        ),
        pytest.param(
            "numeric_pattern_properties_record_wrapper",
            '{"properties":{"Assign":{"type":"object","patternProperties":{"^[0-9]+$":{"type":"object","properties":{"MODE":{"type":"string","enum":["FIRST","SECOND"]}}}}}}}',
            id="numeric_pattern_properties_record_wrapper",
        ),
    ],
)
def test_same_section_schema_record_wrapper_forms_supply_enum_values(
    schema_form: str, record_schema: str, tmp_path: Path
):
    """Both documented record wrappers lead to the same manual field path."""
    path = tmp_path / f"99_DB_{schema_form}.md"
    path.write_text(
        "## 1. `/db/RECORD-WRAPPER` -- Record wrapper\n\n"
        "### JSON Schema\n\n```json\n"
        + record_schema
        + "\n```\n\n"
        "| No. | Description | Key | Value Type | Default | Required |\n"
        "|-----|-------------|-----|------------|---------|----------|\n"
        "| 1 | Mode | `MODE` | String (enum) | - | Required |\n",
        encoding="utf-8",
    )

    mode = ex.parse_chapter(path)[0].tables[0].fields[0]
    assert mode.enum == ["FIRST", "SECOND"]
    assert not mode.notes


def test_same_section_schema_additional_properties_record_map_supplies_array_item_type(tmp_path: Path):
    """An ID-keyed map's value schema retains its child field path exactly."""
    path = tmp_path / "99_DB_AdditionalPropertiesMap.md"
    path.write_text(
        "## 1. `/db/RECORD-MAP` -- Record map\n\n"
        "### JSON Schema\n\n```json\n"
        '{"type":"object","properties":{"Assign":{"type":"object","additionalProperties":{"type":"object","properties":{"SELECTED_MEMBERS":{"type":"object","additionalProperties":{"type":"object","properties":{"ELEM_LIST":{"type":"array","items":{"type":"integer"}}}}}}}}}}\n'
        "```\n\n"
        "| No. | Description | Key | Value Type | Default | Required |\n"
        "|-----|-------------|-----|------------|---------|----------|\n"
        "| 1 | Selected members | `SELECTED_MEMBERS` | Object | - | Required |\n"
        "| 1.1 | Element list | `ELEM_LIST` | Array | - | Required |\n",
        encoding="utf-8",
    )

    selected_members = ex.parse_chapter(path)[0].tables[0].fields[0]
    element_list = selected_members.properties[0]
    assert element_list.items == {"type": "integer"}
    assert not any("array element type not stated" in note for note in element_list.notes)


def test_same_section_schema_expands_compact_one_of_keys_and_rehomes_their_children(tmp_path: Path):
    """A compact selector row is safe only when its exact schema fills every path."""
    path = tmp_path / "99_DB_CompactOneOf.md"
    path.write_text(
        "## 1. `/db/COMPACT-ONE-OF` -- Compact selector\n\n"
        "### JSON Schema\n\n```json\n"
        '{"type":"object","properties":{"Argument":{"type":"object","oneOf":[{"required":["ELEMS"]},{"required":["SECTIONS"]}],"properties":{"ELEMS":{"type":"object","properties":{"KEYS":{"type":"array","items":{"type":"integer"}},"TO":{"type":"string"},"STRUCTURE_GROUP_NAME":{"type":"string"}}},"SECTIONS":{"type":"array","items":{"type":"integer"}}}}}}\n'
        "```\n\n"
        "| No. | Description | Key | Value Type | Default | Required |\n"
        "|-----|-------------|-----|------------|---------|----------|\n"
        "| 1 | Argument wrapper | `Argument` | Object | - | Required |\n"
        "| 2 | Target | `ELEMS` / `SECTIONS` | Object / Array | - | Conditional |\n"
        "| 2.1 | Individual IDs / ID range / structure group | `KEYS` / `TO` / `STRUCTURE_GROUP_NAME` | Array[Int] / String / String | - | Optional |\n",
        encoding="utf-8",
    )

    fields = {field.key: field for field in ex.parse_chapter(path)[0].tables[0].fields}
    elems = fields["ELEMS"]
    sections = fields["SECTIONS"]
    assert [field.key for field in elems.properties] == ["KEYS", "TO", "STRUCTURE_GROUP_NAME"]
    assert elems.properties[0].items == {"type": "integer"}
    assert sections.items == {"type": "integer"}
    assert elems.condition == 'oneOf: exactly one of "ELEMS", "SECTIONS" is required'
    assert sections.condition == elems.condition
    assert not any(_note for field in ex._walk(list(fields.values())) for _note in field.notes if "single field name" in _note)


@pytest.mark.parametrize(
    ("value", "target"),
    [
        pytest.param("MEMB", "CURRENT_MODE_MEMB", id="first_code_spanned_branch"),
        pytest.param("PROP", "CURRENT_MODE_PROP", id="compact_second_code_spanned_branch"),
    ],
)
def test_manual_prose_compact_condition_pair_supplies_applies_when(
    value: str, target: str, tmp_path: Path
):
    """The explicit paired prose form is a condition source, unlike examples."""
    path = tmp_path / "99_DB_ProseConditions.md"
    path.write_text(
        "## 1. `/db/PROSE-CONDITIONS` -- Prose conditions\n\n"
        "| No. | Description | Key | Value Type | Default | Required |\n"
        "|-----|-------------|-----|------------|---------|----------|\n"
        "| 1 | Report type | `REPORT_TYPE` | String | - | Required |\n"
        "| 2 | Member mode | `CURRENT_MODE_MEMB` | String | - | Conditional |\n"
        "| 3 | Property mode | `CURRENT_MODE_PROP` | String | - | Conditional |\n\n"
        '> `REPORT_TYPE="MEMB"`이면 `CURRENT_MODE_MEMB`, `"PROP"`이면 `CURRENT_MODE_PROP`를 사용합니다.\n',
        encoding="utf-8",
    )

    fields = {field.key: field for field in ex.parse_chapter(path)[0].tables[0].fields}
    conditional = fields[target]
    assert conditional.condition == f'REPORT_TYPE="{value}"'
    assert conditional.applies_when == [("REPORT_TYPE", (value,))]
    assert not conditional.notes


@pytest.mark.parametrize(
    ("value", "target"),
    [
        pytest.param("WID+STORY", "CURRENT_MODE_WID_STORY", id="first_parallel_branch"),
        pytest.param("WID", "CURRENT_MODE_WID", id="second_parallel_branch"),
    ],
)
def test_manual_prose_parallel_code_span_conditions_supply_applies_when(
    value: str, target: str, tmp_path: Path
):
    """The Korean 'respectively' form maps only equal-length code-span pairs."""
    path = tmp_path / "99_DB_ParallelProseConditions.md"
    path.write_text(
        "## 1. `/db/PARALLEL-CONDITIONS` -- Parallel prose conditions\n\n"
        "| No. | Description | Key | Value Type | Default | Required |\n"
        "|-----|-------------|-----|------------|---------|----------|\n"
        "| 1 | Report type | `REPORT_TYPE` | String | - | Required |\n"
        "| 2 | Story mode | `CURRENT_MODE_WID_STORY` | String | - | Conditional |\n"
        "| 3 | Wall mode | `CURRENT_MODE_WID` | String | - | Conditional |\n\n"
        '> `REPORT_TYPE`으로 출력 단위(`"WID+STORY"`/`"WID"`)를 정하고 각각 `CURRENT_MODE_WID_STORY`/`CURRENT_MODE_WID`로 모드를 지정합니다.\n',
        encoding="utf-8",
    )

    fields = {field.key: field for field in ex.parse_chapter(path)[0].tables[0].fields}
    conditional = fields[target]
    assert conditional.condition == f'REPORT_TYPE="{value}"'
    assert conditional.applies_when == [("REPORT_TYPE", (value,))]
    assert not conditional.notes


@pytest.mark.parametrize(
    ("selector_schema", "expected_condition"),
    [
        pytest.param('{"const":true}', "OPT_USE=true", id="const_selector_then_required"),
        pytest.param('{"enum":["AUTO","USER"]}', 'MODE ∈ {"AUTO", "USER"}', id="enum_selector_then_required"),
    ],
)
def test_same_section_schema_conditional_required_forms_supply_exact_condition(
    selector_schema: str, expected_condition: str, tmp_path: Path
):
    """Only literal schema selectors resolve a table's otherwise blank condition."""
    path = tmp_path / "99_DB_ConditionalSchema.md"
    path.write_text(
        "## 1. `/db/CONDITIONAL-SCHEMA` -- Conditional schema\n\n"
        "### JSON Schema\n\n```json\n"
        '{"type":"object","properties":{"Assign":{"type":"object","properties":{"OPT_USE":{"type":"boolean"},"MODE":{"type":"string"},"DETAIL":{"type":"number"}},"allOf":[{"if":{"properties":{"'
        + ("OPT_USE" if "OPT_USE" in expected_condition else "MODE")
        + '":'
        + selector_schema
        + '},"required":["'
        + ("OPT_USE" if "OPT_USE" in expected_condition else "MODE")
        + '"]},"then":{"required":["DETAIL"]}}]}}}\n'
        "```\n\n"
        "| No. | Description | Key | Value Type | Default | Required |\n"
        "|-----|-------------|-----|------------|---------|----------|\n"
        "| 1 | Selector | `OPT_USE` | Boolean | - | Optional |\n"
        "| 2 | Mode | `MODE` | String | - | Optional |\n"
        "| 3 | Detail | `DETAIL` | Number | - | Conditional Required |\n",
        encoding="utf-8",
    )

    detail = ex.parse_chapter(path)[0].tables[0].fields[2]
    assert detail.requirement == "conditional"
    assert detail.condition == expected_condition
    assert not detail.notes


def test_schema_conditional_marker_does_not_mask_same_field_enum(tmp_path: Path):
    """A ``then.required`` marker is relation metadata, not a second schema."""
    path = tmp_path / "99_DB_ConditionalEnumSchema.md"
    path.write_text(
        "## 1. `/db/CONDITIONAL-ENUM` -- Conditional enum\n\n"
        "### JSON Schema\n\n```json\n"
        '{"type":"object","properties":{"Assign":{"type":"object","properties":{"MODE":{"type":"string","enum":["AUTO","USER"]},"DETAIL":{"type":"string","enum":["FIRST","SECOND"]}},"allOf":[{"if":{"properties":{"MODE":{"const":"USER"}},"required":["MODE"]},"then":{"required":["DETAIL"]}}]}}}\n'
        "```\n\n"
        "| No. | Description | Key | Value Type | Default | Required |\n"
        "|-----|-------------|-----|------------|---------|----------|\n"
        "| 1 | Mode | `MODE` | String (enum) | - | Optional |\n"
        "| 2 | Detail | `DETAIL` | String (enum) | - | Conditional Required |\n",
        encoding="utf-8",
    )

    detail = ex.parse_chapter(path)[0].tables[0].fields[1]
    assert detail.enum == ["FIRST", "SECOND"]
    assert detail.condition == 'MODE="USER"'
    assert detail.applies_when == [("MODE", ("USER",))]
    assert not detail.notes


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        pytest.param("Use a range (INPUT_METHOD=KEYS)", ("INPUT_METHOD", ("KEYS",)), id="bare_uppercase_value"),
        pytest.param("Material strength (CODE=None)", ("CODE", ("None",)), id="bare_titlecase_value"),
        pytest.param("Two choices (MODE=A, CODE=None)", None, id="multiple_equalities_stay_unverified"),
    ],
)
def test_description_literal_condition_accepts_only_one_explicit_equality(
    description: str, expected: tuple[str, str] | None
):
    assert ex._description_literal_condition(description) == expected


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        pytest.param("Target (same structure as SOURCE)", "SOURCE", id="english_same_structure"),
        pytest.param("Target (구조는 Part A와 동일)", "PART_A", id="korean_same_structure"),
        pytest.param("Target object", None, id="no_explicit_inheritance"),
    ],
)
def test_same_object_shape_reference_requires_an_explicit_manual_statement(
    description: str, expected: str | None
):
    assert ex._same_object_shape_reference(description) == expected


def test_explicit_same_object_structure_clones_only_parsed_sibling_children(tmp_path: Path):
    path = tmp_path / "99_DB_SameStructure.md"
    path.write_text(
        "## 1. `/db/SAME-STRUCTURE` -- Same object structure\n\n"
        "| No. | Description | Key | Value Type | Default | Required |\n"
        "|-----|-------------|-----|------------|---------|----------|\n"
        "| 1 | Source object | `SOURCE` | Object | - | Required |\n"
        "| 1.1 | Input method | `INPUT_METHOD` | String | - | Required |\n"
        "| 1.2 | Source child (INPUT_METHOD=KEYS) | `CHILD` | String | - | Conditional Required |\n"
        "| 2 | Target (same structure as SOURCE) | `TARGET` | Object | - | Required |\n",
        encoding="utf-8",
    )

    fields, _ = ex._structural_fields(ex.parse_chapter(path)[0])
    target = next(field for field in fields if field.key == "TARGET")
    assert [field.key for field in target.properties] == ["INPUT_METHOD", "CHILD"]
    assert not target.properties[1].notes

    draft = yaml.safe_load(ex.render_draft(ex.parse_chapter(path)[0]))
    target_draft = next(field for field in draft["fields"] if field["key"] == "TARGET")
    child = target_draft["properties"][1]
    assert child["appliesWhen"] == [{"path": "TARGET.INPUT_METHOD", "equals": "KEYS"}]


def test_repeated_child_key_is_retained_under_each_numbered_parent(tmp_path: Path):
    path = tmp_path / "99_DB_RepeatedChild.md"
    path.write_text(
        "## 1. `/db/REPEATED-CHILD` -- Repeated child key\n\n"
        "| No. | Description | Key | Value Type | Default | Required |\n"
        "|-----|-------------|-----|------------|---------|----------|\n"
        "| 1 | First object | `FIRST` | Object | - | Required |\n"
        "| 1.1 | First code | `CODE` | String | - | Required |\n"
        "| 2 | Second object | `SECOND` | Object | - | Required |\n"
        "| 2.1 | Second code | `CODE` | String | - | Required |\n",
        encoding="utf-8",
    )

    fields = ex.parse_chapter(path)[0].tables[0].fields
    assert [field.key for field in fields[0].properties] == ["CODE"]
    assert [field.key for field in fields[1].properties] == ["CODE"]


@pytest.mark.parametrize(
    ("table_default", "schema_default", "expected_default", "expected_note"),
    [
        pytest.param(
            "AUTO",
            '"AUTO"',
            "AUTO",
            None,
            id="matching_schema_string_confirms_bare_default",
        ),
        pytest.param(
            "AUTO",
            '"MANUAL"',
            None,
            "AUTO",
            id="different_schema_default_preserves_manual_prose_note",
        ),
    ],
)
def test_schema_default_confirms_only_the_same_bare_table_default(
    table_default: str,
    schema_default: str,
    expected_default: str | None,
    expected_note: str | None,
    tmp_path: Path,
):
    path = tmp_path / "99_DB_BareDefault.md"
    path.write_text(
        "## 1. `/db/BARE-DEFAULT` -- Bare default\n\n"
        "### JSON Schema\n\n```json\n"
        '{"type":"object","properties":{"Assign":{"type":"object","properties":{"MODE":{"type":"string","default":'
        + schema_default
        + "}}}}}\n```\n\n"
        "| No. | Description | Key | Value Type | Default | Required |\n"
        "|-----|-------------|-----|------------|---------|----------|\n"
        f"| 1 | Mode | `MODE` | String | {table_default} | Optional |\n",
        encoding="utf-8",
    )

    mode = ex.parse_chapter(path)[0].tables[0].fields[0]
    assert mode.documented_default == expected_default
    assert mode.documented_default_note == expected_note
    assert not any(note.startswith("non-literal default ") for note in mode.notes)


@pytest.mark.parametrize(
    "manual_default",
    [
        pytest.param("System", id="system_word_is_a_manual_note_not_a_wire_value"),
        pytest.param("ADD, REPLACE", id="comma_separated_prose_is_a_manual_note_not_a_wire_value"),
    ],
)
def test_nonliteral_default_renders_as_documented_default_note(manual_default: str, tmp_path: Path):
    path = tmp_path / "99_DB_NonliteralDefault.md"
    path.write_text(
        "## 1. `/db/NONLITERAL-DEFAULT` -- Nonliteral default\n\n"
        "| No. | Description | Key | Value Type | Default | Required |\n"
        "|-----|-------------|-----|------------|---------|----------|\n"
        f"| 1 | Mode | `MODE` | String | {manual_default} | Optional |\n",
        encoding="utf-8",
    )

    draft = yaml.safe_load(ex.render_draft(ex.parse_chapter(path)[0]))
    field = draft["fields"][0]
    assert field["documentedDefault"] is None
    assert field["documentedDefaultNote"] == manual_default


def test_shipped_contracts_still_match_the_manual_if_it_is_present():
    """Runs only where the sibling manual repo is checked out - CI does both."""
    manual_repo = ex.DEFAULT_MANUAL_REPO
    if not (manual_repo / "docs" / "manual").is_dir():
        pytest.skip("manual repo not available")

    assert ex.run_check(ex.load_manual(manual_repo)[0]) == 0


BACKSLASH = chr(92)


def test_an_escaped_pipe_does_not_delete_the_row_it_appears_in(tmp_path: Path):
    r"""``\|`` is a literal pipe inside a cell, not a column boundary.

    The manual writes alternatives as ``None \| 50% \| 100%``. Splitting
    the row on every ``|`` gave it more cells than its header, and a row whose
    cell count disagrees is dropped, so the field vanished with no diagnostic.
    Ten rows across three chapters were lost that way -- among them
    ``/ope/LCOM-GEN``'s ``CODE_SELECTION``, which the same section's JSON
    Schema marks **required** and uses to select the whole request body.
    """

    path = tmp_path / "99_DB_Escaped.md"
    path.write_text(
        r"""## 1. `/db/ESCAPED` -- escaped pipe

### JSON Schema

```json
{
  "ESCAPED": {
    "type": "object",
    "properties": {
      "OPTION": { "description": "Option", "type": "string" },
      "SPLICED_BARS": { "description": "Splice", "type": "string" }
    }
  }
}
```

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Option | `"OPTION"` | String | - | Optional |
| 2 | Splice option (`None` \| `50%` \| `100%`) | `"SPLICED_BARS"` | String | `"50%"` | Optional |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    assert [field.key for field in section.tables[0].fields] == ["OPTION", "SPLICED_BARS"]
    # The escape belongs to the markdown, not to the documented text.
    spliced = section.tables[0].fields[1]
    assert spliced.description == "Splice option (None | 50% | 100%)"
    assert BACKSLASH not in spliced.description
    # A row the table does name is not a schema-only root.
    assert section.schema_only_roots == ()


def test_backticked_parallel_keys_are_read_like_quoted_ones(tmp_path: Path):
    """`A` / `B` and "A" / "B" are the same claim in different typography.

    Chapter 14 writes its compact two-key rows with backticks. The parallel-cell
    reader only recognised double quotes, so those rows became one field with a
    compound key and `/db/POGD` could not be promoted. A row that shares one
    type and states no Default or Required column cannot be assigning different
    claims to its keys, which is what makes repeating the shared claim safe.
    """

    path = tmp_path / "99_DB_Parallel.md"
    path.write_text(
        """## 1. `/db/PARALLEL` -- backticked parallel keys

### Specifications

| Group | Key | Description | Value Type |
|---|---|---|---|
| fibre | `CORE_DIV_Y` / `CORE_DIV_Z` | Core divisions | Integer |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    assert [field.key for field in section.tables[0].fields] == ["CORE_DIV_Y", "CORE_DIV_Z"]
    assert {field.type for field in section.tables[0].fields} == {"integer"}


def test_two_keys_the_manual_calls_alternatives_are_not_split():
    """`FREQ1`/`PERIOD1` is one field named two ways, not two fields.

    Its description says frequency when COEF_CALC=0 and period when
    COEF_CALC=1, so splitting the row would declare that a caller may send
    both. The row keeps a Default and a Required column, which is exactly the
    evidence that its columns are not per-key, and the reader refuses it.
    """

    assert ex._parallel_field_cells("`FREQ1`/`PERIOD1`", "Number", "-", "Required", "3") is None
    assert ex._parallel_field_cells("`FREQ2`/`PERIOD2`", "Number", "-", "Required", "5") is None


def test_reviewed_homogeneous_slash_row_can_repeat_its_shared_claims():
    assert ex._parallel_field_cells(
        '`SCALE_FACTOR1`/`SCALE_FACTOR2`/`SCALE_FACTOR3`',
        "Number",
        "-",
        "Required (LM5)",
        "15",
        allow_shared_slash=True,
    ) == [
        ("SCALE_FACTOR1", "Number", "-", "Required (LM5)"),
        ("SCALE_FACTOR2", "Number", "-", "Required (LM5)"),
        ("SCALE_FACTOR3", "Number", "-", "Required (LM5)"),
    ]


def test_reviewed_mixed_type_row_repeats_only_shared_default_and_required_cells():
    """STCT maps three types positionally while sharing the row-level claims."""
    assert ex._parallel_field_cells(
        '`"bSD"` / `"iSDOPT"` / `"SDCONST"`',
        "Boolean / Integer / Number",
        "-",
        "Optional",
        "-",
        allow_shared_default_required=True,
    ) == [
        ("bSD", "Boolean", "-", "Optional"),
        ("iSDOPT", "Integer", "-", "Optional"),
        ("SDCONST", "Number", "-", "Optional"),
    ]


@pytest.mark.parametrize(
    ("key_cell", "type_cell", "expected_keys"),
    [
        pytest.param(
            '`"bENEG"` / `"EV"`',
            "Boolean / Number",
            ["bENEG", "EV"],
            id="energy-norm-boolean-and-value",
        ),
        pytest.param(
            '`"bDISP"` / `"DV"`',
            "Boolean / Number",
            ["bDISP", "DV"],
            id="displacement-norm-boolean-and-value",
        ),
        pytest.param(
            '`"bFORC"` / `"FV"`',
            "Boolean / Number",
            ["bFORC", "FV"],
            id="force-norm-boolean-and-value",
        ),
        pytest.param(
            '`"bTTLE_ES"` / `"iTTLE_ES"`',
            "Boolean / Integer",
            ["bTTLE_ES", "iTTLE_ES"],
            id="elastic-loss-boolean-and-type",
        ),
    ],
)
def test_stct_reviewed_mixed_rows_repeat_their_row_level_claims(
    key_cell: str, type_cell: str, expected_keys: list[str]
):
    parsed = ex._parallel_field_cells(
        key_cell,
        type_cell,
        "-",
        "Optional",
        "-",
        allow_shared_default_required=True,
    )
    assert parsed is not None
    assert [key for key, *_ in parsed] == expected_keys


def test_stct_reviewed_time_gap_row_repeats_its_homogeneous_claims():
    parsed = ex._parallel_field_cells(
        '`"iT10"` / `"iT100"` / `"iT1K"` / `"iT5K"` / `"iT10K"`',
        "Integer",
        "-",
        "Optional",
        "-",
        allow_shared_slash=True,
    )
    assert parsed is not None
    assert [key for key, *_ in parsed] == ["iT10", "iT100", "iT1K", "iT5K", "iT10K"]


def test_mixed_optional_and_required_branches_remain_conditional():
    raw = "Optional (LM1) / Required (LM3/4, Optimization)"
    assert ex._normalize_requirement(raw) == ("conditional", raw, None)


def test_reviewed_condition_is_taken_from_the_same_section_only():
    field = _field("1", "RIGID_PARAM", "Object")
    field.requirement = "conditional"
    field.notes = ["the manual marks this conditional but does not state the condition"]
    ex._apply_reviewed_field_conditions("/ope/GUSTFACTOR", [field])
    assert field.condition == "STRUCTURE_TYPE = RIGID인 경우"
    assert field.applies_when == [("STRUCTURE_TYPE", ("RIGID",))]
    assert all("does not state" not in note for note in field.notes)


@pytest.mark.parametrize(
    ("key", "requirement", "placeholder", "expected_condition", "expected_applies_when"),
    [
        pytest.param(
            "GROUP",
            "conditional",
            "조건부",
            'ITD="GROUP"일 때',
            [("ITD", ("GROUP",))],
            id="conditional-placeholder-uses-description-selector",
        ),
        pytest.param(
            "bTRUSS",
            "optional",
            None,
            "when bCONV true",
            [("bCONV", (True,))],
            id="optional-field-keeps-explicit-use-condition",
        ),
    ],
)
def test_stct_reviewed_field_conditions_preserve_the_manual_selector(
    key: str,
    requirement: str,
    placeholder: str | None,
    expected_condition: str,
    expected_applies_when: list[tuple[str, tuple[object, ...]]],
):
    field = _field("1", key, "String")
    field.requirement = requirement
    field.condition = placeholder
    ex._apply_reviewed_field_conditions("/db/STCT", [field])
    assert field.condition == expected_condition
    assert field.applies_when == expected_applies_when


@pytest.mark.parametrize(
    ("key_cell", "type_cell", "expected"),
    [
        (
            "OPTION.EQUAL_OPTION.{NUM_X,NUM_Y,NUM_Z}",
            "Integer",
            [
                ("OPTION.EQUAL_OPTION.NUM_X", "Integer", None, "Required"),
                ("OPTION.EQUAL_OPTION.NUM_Y", "Integer", None, "Required"),
                ("OPTION.EQUAL_OPTION.NUM_Z", "Integer", None, "Required"),
            ],
        ),
        (
            "OPTION.PARALLEL_OPTION.{NUM_OF_DIVISIONS,MAIN_POST_ELEM}",
            "Integer/Array",
            [
                ("OPTION.PARALLEL_OPTION.NUM_OF_DIVISIONS", "Integer", None, "Required"),
                ("OPTION.PARALLEL_OPTION.MAIN_POST_ELEM", "Array", None, "Required"),
            ],
        ),
    ],
    ids=("homogeneous-members", "parallel-member-types"),
)
def test_braced_key_sets_expand_under_their_documented_parent(
    key_cell: str,
    type_cell: str,
    expected: list[tuple[str, str | None, str | None, str | None]],
):
    assert ex._parallel_field_cells(key_cell, type_cell, None, "Required", "") == expected


@pytest.mark.parametrize(
    ("cell", "key", "annotation"),
    [
        (
            '`RCDGNCODE` · "KISTEC2019" / "KISTEC2013" / "MOE2019"',
            "`RCDGNCODE`",
            '"KISTEC2019" / "KISTEC2013" / "MOE2019"',
        ),
        ('`LOC_BEAM` · I단: "I" / J단: "J" / 중앙: "M"', "`LOC_BEAM`", 'I단: "I" / J단: "J" / 중앙: "M"'),
        ('`PLAIN`', '`PLAIN`', ""),
    ],
    ids=("quoted-values", "labelled-values", "no-annotation"),
)
def test_key_column_value_annotations_are_not_wire_properties(
    cell: str, key: str, annotation: str
):
    assert ex._key_cell_annotation(cell) == (key, annotation)


def test_a_compact_row_its_own_schema_names_key_by_key_is_split(tmp_path: Path):
    """The schema says whether a slash joins two fields or renames one.

    Chapter 26 compresses two fields into ``"DT" / "DB" | Number | 0``. The row
    alone cannot say whether a caller sends both keys or picks between two
    names for one, and `/db/THIS-M1` writes the second kind - which is why the
    reader refuses every such row on the cells alone. Where the section's own
    JSON Schema declares each key as a property of its own, they are separate
    wire names, and it also states the type, requiredness and default the
    compressed row had to share.
    """

    path = tmp_path / "99_DB_CompactSchema.md"
    path.write_text(
        """## 1. `/db/COMPACT` -- compact rows the schema resolves

### JSON Schema

```json
{
  "COMPACT": {
    "type": "object",
    "properties": {
      "BEAM": {
        "type": "object",
        "properties": {
          "DT": { "type": "number", "description": "Top cover", "default": 0 },
          "DB": { "type": "number", "description": "Bottom cover", "default": 0 },
          "DOUBLY_REBAR": { "type": "boolean", "description": "Doubly", "default": true },
          "DOUBLY_K": { "type": "number", "description": "k factor", "default": 1 }
        }
      }
    }
  }
}
```

### Specifications

**Root**

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Beam criteria | `"BEAM"` | Object | - | Optional |

**`BEAM` object**

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| a | Top / bottom cover | `"DT"` / `"DB"` | Number | `0` | Optional |
| b | Doubly design / k | `"DOUBLY_REBAR"` / `"DOUBLY_K"` | Boolean / Number | `true` / `1` | Optional |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    beam = section.tables[1].fields
    assert [field.key for field in beam] == ["DT", "DB", "DOUBLY_REBAR", "DOUBLY_K"]
    # Each key takes the claim the schema makes about it, not the row's shared one.
    assert [field.type for field in beam] == ["number", "number", "boolean", "number"]
    assert [field.documented_default for field in beam] == [0, 0, True, 1]
    # The row described all of them at once; the schema describes each.
    assert [field.description for field in beam] == ["Top cover", "Bottom cover", "Doubly", "k factor"]
    assert all(not field.notes for field in beam)


def test_a_compact_row_no_schema_names_keeps_its_review_note(tmp_path: Path):
    """A slash the schema cannot vouch for is still an unanswered question.

    `/db/THIS-M1`'s ``FREQ1/PERIOD1`` is one field the manual names two ways -
    a frequency under one `COEF_CALC` value and a period under the other - and
    its schema declares neither name. Splitting it would publish two fields
    that do not exist, so the row stays whole and keeps the note that says so.
    """

    path = tmp_path / "99_DB_CompactUnnamed.md"
    path.write_text(
        """## 1. `/db/ALTERNATIVE` -- a compact row naming one field twice

### JSON Schema

```json
{
  "ALTERNATIVE": {
    "type": "object",
    "properties": {
      "COEF_CALC": { "type": "integer", "description": "0 frequency, 1 period" }
    }
  }
}
```

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Selector | `"COEF_CALC"` | Integer | `0` | Optional |
| 2 | Frequency when 0, period when 1 | `"FREQ1"` / `"PERIOD1"` | Number | `0` | Optional |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    keys = [field.key for field in section.tables[0].fields]
    assert keys == ["COEF_CALC", 'FREQ1" / "PERIOD1']
    compact = section.tables[0].fields[1]
    assert any(ex._AMBIGUOUS_WIRE_KEY_NOTE in note for note in compact.notes)


def test_a_member_object_table_is_read_under_the_object_it_describes(tmp_path: Path):
    """A table of an object's fields is not a table of the request's roots.

    Chapter 26 heads one table per member object rather than nesting the rows
    under a parent row, so none of those rows is a root property and every
    schema hint missed them: the KDS rebar sections were transcribed without a
    single enum or requiredness the schema states, purely because of where the
    manual put the row. A table is placed under an object only when no row of
    it names a root property and that object declares every row it has.
    """

    path = tmp_path / "99_DB_MemberTable.md"
    path.write_text(
        """## 1. `/db/MEMBER` -- one table per member object

### JSON Schema

```json
{
  "MEMBER": {
    "type": "object",
    "properties": {
      "WALL": {
        "type": "object",
        "required": ["GRADE"],
        "properties": {
          "GRADE": { "type": "string", "description": "Grade", "enum": ["SD400", "SD500"] },
          "SPACING": { "type": "number", "description": "Spacing", "default": 0.2 }
        }
      }
    }
  }
}
```

### Specifications

**Root**

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Wall criteria | `"WALL"` | Object | - | Optional |

**`WALL` object**

| No. | Description | Key | Value Type |
|---|---|---|---|
| a | Rebar grade | `"GRADE"` | String (enum) |
| b | Spacing | `"SPACING"` | Number |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    grade, spacing = section.tables[1].fields
    assert grade.enum == ["SD400", "SD500"]
    assert grade.requirement == "required"
    assert spacing.requirement == "optional"
    assert spacing.documented_default == 0.2


def test_a_bound_stated_for_another_kind_of_value_is_not_transcribed(tmp_path: Path):
    """`minItems` on an integer is the manual disagreeing with itself.

    `/DESIGN/RC/KDS-41-20-2022/REBR` declares ``NUM`` as an integer and bounds
    it with ``minItems: 4`` while its table reads "min 4". The bound is real
    and the keyword that carries it is not one an integer has, so publishing it
    would put a restriction on the field that restricts nothing. Record the
    disagreement and transcribe neither half.
    """

    path = tmp_path / "99_DB_Bound.md"
    path.write_text(
        """## 1. `/db/BOUND` -- a bound on the wrong kind of value

### JSON Schema

```json
{
  "BOUND": {
    "type": "object",
    "properties": {
      "NUM": { "type": "integer", "description": "Bar count", "minItems": 4 },
      "NAMES": { "type": "array", "description": "Bar names", "minItems": 2 }
    }
  }
}
```

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Bar count (min 4) | `"NUM"` | Integer | - | Optional |
| 2 | Bar names | `"NAMES"` | Array[String] | - | Optional |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    num, names = section.tables[0].fields
    assert "minItems" not in num.constraints
    assert any("does not apply to" in note for note in num.notes)
    # The same keyword on the kind of value it does bound is transcribed.
    assert names.constraints["minItems"] == 2
    assert not names.notes


def test_a_list_this_section_already_proved_a_sample_is_one_everywhere(tmp_path: Path):
    """The sentence that says "these are the first five" is written once.

    Chapter 26 states its rebar-size list is 5 of 19 on the fields that carry a
    description and then writes the identical five values, with no description
    at all, on REBB's `NAME`. It is one list abbreviated once. Judging each
    field alone publishes the abbreviation on exactly the fields the manual
    forgot to annotate - a union that makes every bar size from D10 up
    untypeable, which is the defect 2.7.4 shipped and had to correct.
    """

    path = tmp_path / "99_DB_SectionSample.md"
    path.write_text(
        """## 1. `/db/SECTION-SAMPLE` -- one abbreviated list, annotated once

### JSON Schema

```json
{
  "SECTION-SAMPLE": {
    "type": "object",
    "properties": {
      "MAIN_REBAR": { "type": "string", "enum": ["D4", "D5", "D6", "D7", "D8"] },
      "NAME": { "type": "string", "enum": ["D4", "D5", "D6", "D7", "D8"] },
      "SPLICED_BARS": { "type": "string", "enum": ["None", "50%", "100%"] }
    }
  }
}
```

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Main rebar size, 19종 | `"MAIN_REBAR"` | String (enum) | - | Optional |
| 2 | Bar name | `"NAME"` | String (enum) | - | Optional |
| 3 | Splice option | `"SPLICED_BARS"` | String (enum) | - | Optional |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    main, name, spliced = section.tables[0].fields
    assert not main.enum and "19 values and lists 5" in " ".join(main.notes)
    assert not name.enum
    assert any("writes the same list for 'MAIN_REBAR'" in note for note in name.notes)
    # A list nothing in the section calls abbreviated is still transcribed.
    assert spliced.enum == ["None", "50%", "100%"]


def test_the_schema_is_read_again_once_the_tables_are_in_place(tmp_path: Path):
    """A row's path is only correct after its table has been merged.

    The schema starts inside `Assign`, which is message transport; a table row
    written `Assign.GRADE` is at that path only in the assembled request. Read
    per table while parsing, the two spellings never meet, so the same
    section's own enum went untranscribed. Reading the schema a second time
    against the finished paths reaches it, and because it only fills blanks it
    cannot overrule what the first reading already settled.
    """

    path = tmp_path / "99_DB_Wrapped.md"
    path.write_text(
        """## 1. `/db/WRAPPED` -- an Assign-wrapped request

### JSON Schema

```json
{
  "type": "object",
  "properties": {
    "Assign": {
      "type": "object",
      "properties": {
        "GRADE": { "type": "string", "description": "Grade", "enum": ["A", "B"] },
        "COUNT": { "type": "integer", "description": "Count" }
      }
    }
  }
}
```

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Record map | `"Assign"` | Object | - | Required |
| 1-1 | Grade | `"Assign.GRADE"` | String (enum) | - | Optional |
| 1-2 | Count | `"Assign.COUNT"` | Integer | - | Optional |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    parsed = section.tables[0].fields[0].properties[0]
    assert parsed.key == "GRADE" and not parsed.enum
    fields, _ = ex._structural_fields(section)
    merged = fields[0].properties[0]
    assert merged.key == "GRADE"
    assert merged.enum == ["A", "B"]
    assert ex._ENUM_VALUES_ELSEWHERE not in merged.notes


def test_rows_the_manual_all_numbers_as_children_stay_siblings(tmp_path: Path):
    """`(1)` is a depth, not a parent.

    A supplementary table that describes one item structure numbers every row
    `(1)`-`(5)` and has no parent row of its own. Recording the first at depth
    zero made it the parent of its own siblings: `/db/RCHK`'s `LAYER` became an
    object holding `dD` and `BAR_NUM`, and `/db/RPSC`'s boolean `OPT_DR` an
    object holding the twenty fields after it, both of which those sections'
    request examples write beside them.
    """

    path = tmp_path / "99_DB_Orphan.md"
    path.write_text(
        """## 1. `/db/ORPHAN` -- a table whose rows are all numbered as children

### Specifications

**`ITEM` structure**

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| (1) | Layer number | `"LAYER"` | Integer | - | Required |
| (2) | Cover | `"dD"` | Number | - | Required |
| (3) | Bar count | `"BAR_NUM"` | Integer | - | Required |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    fields = section.tables[0].fields
    assert [field.key for field in fields] == ["LAYER", "dD", "BAR_NUM"]
    assert all(not field.properties for field in fields)
    assert [field.type for field in fields] == ["integer", "number", "integer"]


def test_a_named_parent_still_adopts_the_rows_numbered_under_it(tmp_path: Path):
    """The common form - a plain-numbered parent then `(1)`, `(2)` - is intact.

    59 promoted contracts nest this way. The orphan rule above must separate
    "no parent row exists" from "the parent row is right there".
    """

    path = tmp_path / "99_DB_Parented.md"
    path.write_text(
        """## 1. `/db/PARENTED` -- a named parent with numbered children

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Items | `"ITEMS"` | Array[Object] | - | Required |
| (1) | Layer number | `"LAYER"` | Integer | - | Required |
| (2) | Cover | `"dD"` | Number | - | Required |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    items = section.tables[0].fields[0]
    assert items.key == "ITEMS"
    assert [child.key for child in items.properties] == ["LAYER", "dD"]


def test_a_value_type_the_same_section_contradicts_is_not_transcribed(tmp_path: Path):
    """Two renderings of one property that cannot both be right.

    Where a table compresses or omits, the schema completes it. Here they state
    different things: `/db/SBDO` types `AXIS_VECTOR` Number in its table and an
    array of numbers in its schema, and sends `[0, 0, 0, 0, 0, 0]` in its own
    Request Example. Reading the table alone published an npm field a caller
    cannot assign the documented value to. Choosing between them takes evidence
    this function does not have, so it takes neither and says so.
    """

    path = tmp_path / "99_DB_TypeClash.md"
    path.write_text(
        """## 1. `/db/TYPE-CLASH` -- a table and a schema that disagree

### JSON Schema

```json
{
  "TYPE-CLASH": {
    "type": "object",
    "properties": {
      "AXIS_VECTOR": { "type": "array", "items": { "type": "number" } },
      "ANGLE": { "type": "number" }
    }
  }
}
```

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Axis vector | `"AXIS_VECTOR"` | Number | `0` | Optional |
| 2 | Angle | `"ANGLE"` | Number | `0` | Optional |
""",
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    vector, angle = section.tables[0].fields
    # The table's claim stands, unconfirmed, and the schema's is not adopted.
    assert vector.type == "number"
    assert any("JSON Schema types it 'array'" in note for note in vector.notes)
    # A row the two agree on says nothing.
    assert angle.type == "number" and not angle.notes

# A cut-down `/db/MATL` section: the endpoint name matters, because the curated
# type correction and the conditional-table placement are both keyed by it.
_MATL_SECTION = """## 1. `/db/MATL` -- Material Properties

### JSON Schema

```json
{
  "MATL": {
    "type": "object",
    "properties": {
      "TYPE": { "type": "string" },
      "PARAM": { "description": "Material Data", "type": "array" }
    }
  }
}
```

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Material Type | `"TYPE"` | String | - | Required |
| 9 | Material Parameter | `"PARAM"` | Object | - | Required |
| (1) | Material Parameter Type | `"P_TYPE"` | Integer | - | Required |

#### PARAM -- P_TYPE = 1 (Standard / DB)

| Sub-No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| (2) | Standard Name | `"STANDARD"` | String | - | Required |
| (3) | Code Name | `"CODE"` | String | Blank | Optional |

#### PARAM -- P_TYPE = 2 (Isotropic / User)

| Sub-No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| (2) | Modulus of Elasticity | `"ELAST"` | Number | - | Required |
| (3) | Weight Density | `"DEN"` | Number | - | Required |

#### PARAM -- P_TYPE = 3 (Orthotropic / User)

| Sub-No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| (2) | Modulus of Elasticity (3 values) | `"ELAST_M"` | Array[Number,3] | - | Required |
| (3) | Weight Density | `"DEN"` | Number | - | Required |
"""


def _matl_section(tmp_path: Path):
    path = tmp_path / "99_DB_Matl.md"
    path.write_text(_MATL_SECTION, encoding="utf-8")
    return ex.parse_chapter(path)[0]


def test_a_value_type_review_resolved_is_written_with_its_evidence(tmp_path: Path):
    """The reviewed resolution of a self-contradicting Value Type, and why.

    The extractor refuses to choose between a table and a schema that disagree,
    because choosing takes the section's Request Example and the SDK that
    already sends that shape. `/db/SBDO` and `/db/MATL` are the two whose
    resolution has been checked against both, so they carry the corrected type
    and a `manualDefects` entry - the record a manual re-sync has to argue with
    rather than silently win against.
    """

    draft = ex.render_draft(_matl_section(tmp_path))
    document = yaml.safe_load(draft)
    param = next(field for field in document["fields"] if field["key"] == "PARAM")
    assert param["type"] == "array"
    assert param["items"] == {"type": "object"}
    defects = document["manualDefects"]
    assert [entry["describes"] for entry in defects] == ["field_value"]
    assert "Object" in defects[0]["manualSays"]
    assert "MD-11" in defects[0]["evidence"]
    # The correction replaces the review note; nothing is left unresolved.
    assert "JSON Schema types it" not in draft


def test_a_branch_table_that_names_its_object_lands_inside_it(tmp_path: Path):
    """`#### PARAM - P_TYPE = 1` describes a PARAM entry, not the request.

    Merged at the root those rows become an endpoint-level branch, and the npm
    generator built `MaterialPayload & {P_TYPE: 1; STANDARD: string; ...}` -
    `STANDARD` beside `TYPE` and `NAME`, where no payload has ever carried it.
    The section's own Request Example, and the Python TypedDict, put every one
    of them inside a `PARAM` entry.
    """

    section = _matl_section(tmp_path)
    fields, _ = ex._structural_fields(section)
    fields, _ = ex._conditional_fields(section, fields)
    assert {field.key for field in fields} == {"TYPE", "PARAM"}
    param = next(field for field in fields if field.key == "PARAM")
    assert {"P_TYPE", "STANDARD", "CODE", "ELAST", "DEN", "ELAST_M"} == {
        child.key for child in param.properties
    }


def test_a_field_two_branch_tables_document_applies_under_both(tmp_path: Path):
    """`DEN` is listed under P_TYPE 2 and again under P_TYPE 3.

    `appliesWhen` entries are combined with AND, so keeping the first table's
    condition and adding the second would be a contradiction rather than a
    widening - and keeping only the first says an orthotropic material may not
    carry a density. The values merge into the one `in` the schema has for
    exactly this.
    """

    section = _matl_section(tmp_path)
    fields, _ = ex._structural_fields(section)
    fields, _ = ex._conditional_fields(section, fields)
    param = next(field for field in fields if field.key == "PARAM")
    by_key = {child.key: child for child in param.properties}
    assert by_key["DEN"].applies_when == [("P_TYPE", (2, 3))]
    # A field only one table documents keeps the one value.
    assert by_key["ELAST"].applies_when == [("P_TYPE", (2,))]
    assert by_key["STANDARD"].applies_when == [("P_TYPE", (1,))]


def test_a_finding_nothing_can_reopen_renders_as_resolved(tmp_path: Path):
    """A conclusion and an open question do not deserve the same marker.

    Promotion refuses a draft still carrying `# NOTE:`, which is right for a
    gap and wrong for an answer. Deciding which is which belongs where the
    evidence is - the extractor knows the sampled-enum rule fired and why -
    so it renders a settled finding `# RESOLVED:`. Reading the sampled-enum
    conclusion as unresolved held three contracts out of the source of truth
    as though someone still had to choose.
    """

    path = tmp_path / "99_DB_Resolved.md"
    path.write_text(
        """## 1. `/db/RESOLVED-MARK` -- a settled finding and an open one

### JSON Schema

```json
{
  "RESOLVED-MARK": {
    "type": "object",
    "properties": {
      "MAIN_REBAR": { "type": "string", "enum": ["D4", "D5"] },
      "WIDTH": { "type": "number" }
    }
  }
}
```

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Main rebar size, 19종 | `"MAIN_REBAR"` | String (enum) | - | Optional |
| 2 | Width | `"WIDTH"` | String | - | Optional |
""",
        encoding="utf-8",
    )

    draft = ex.render_draft(ex.parse_chapter(path)[0])
    resolved = [line.strip() for line in draft.splitlines() if line.strip().startswith("# RESOLVED:")]
    notes = [line.strip() for line in draft.splitlines() if line.strip().startswith("# NOTE:")]
    # The sampled enum is an answer: nothing in the manual holds the members
    # its own description says it withheld.
    assert any("19 values" in line for line in resolved)
    # A Value Type the section contradicts is a question, and still blocks.
    # A wrapped note keeps its marker only on the first line, which is the
    # line promotion reads, so match on that.
    assert any("Specifications table types this" in line for line in notes)
    assert not any("Specifications table types this" in line for line in resolved)



def _field(number: str, key: str, declared: str) -> "ex.ParsedField":
    """A parsed row, as the No. column and Key column give it."""

    return ex.ParsedField(key, key, declared, None, "required", None, number=number)


def test_a_child_the_manual_marks_with_a_bare_letter_lands_inside_its_parent():
    """`/db/SWIND` marks a member of an object row with `a`, `b`, `c`.

    The No. column's parenthesised `(1)` was the only child marker the parser
    knew, so 183 rows across 18 sections were read as top-level fields of the
    request. `/db/SWIND` gives `OPT_USE` to both `TOPOGRAPHIC_EFFECT` and
    `FORCE_COEF`; flattened, the second overwrote the first and a documented
    field disappeared entirely.
    """

    fields = ex._nest(
        [
            _field("1", "INPUT_METHOD", "integer"),
            _field("", "TOPOGRAPHIC_EFFECT", "object"),
            _field("a", "OPT_USE", "boolean"),
            _field("b", "KZT", "number"),
            _field("", "FORCE_COEF", "object"),
            _field("a", "OPT_USE", "boolean"),
        ]
    )

    assert [field.key for field in fields] == [
        "INPUT_METHOD",
        "TOPOGRAPHIC_EFFECT",
        "FORCE_COEF",
    ]
    assert [child.key for child in fields[1].properties] == ["OPT_USE", "KZT"]
    assert [child.key for child in fields[2].properties] == ["OPT_USE"]


def test_a_bare_marker_after_another_bare_marker_stays_its_sibling():
    """Chapter 26 enumerates a request's own top-level members `a`, `b`, `c`.

    Reading the marker as "one deeper" without looking at the row before it
    buried `MAIN_BAR_BOT` inside `MAIN_BAR_TOP`. The marker says "another
    item", never how deep.
    """

    fields = ex._nest(
        [
            _field("a", "MAIN_BAR_TOP", "object"),
            _field("b", "MAIN_BAR_BOT", "object"),
            _field("c", "SHEAR_BAR", "object"),
        ]
    )

    assert [field.key for field in fields] == [
        "MAIN_BAR_TOP",
        "MAIN_BAR_BOT",
        "SHEAR_BAR",
    ]
    assert all(not field.properties for field in fields)


def test_a_roman_sub_item_goes_under_the_object_the_manual_numbered():
    """`/db/HHCT` numbers `7` > `(1)`-`(3)` > `i`/`ii`.

    Its third level made `TOL`, a `Number`, the parent of the branch that
    follows it, because `i`/`ii` were read as root rows and the next `(3)`
    then attached to the last of them.
    """

    fields = ex._nest(
        [
            _field("7", "ITEM", "object"),
            _field("(1)", "TYPE", "string"),
            _field("(3)", "M_GENERAL", "object"),
            _field("i", "ITER", "integer"),
            _field("ii", "TOL", "number"),
            _field("(3)", "M_EFF_MOD", "object"),
            _field("i", "PHI1", "number"),
        ]
    )

    assert [field.key for field in fields] == ["ITEM"]
    item = fields[0]
    assert [child.key for child in item.properties] == ["TYPE", "M_GENERAL", "M_EFF_MOD"]
    general = item.properties[1]
    assert [child.key for child in general.properties] == ["ITER", "TOL"]
    assert general.properties[1].type == "number"
    assert not general.properties[1].properties
    assert [child.key for child in item.properties[2].properties] == ["PHI1"]


def test_a_word_in_the_no_column_is_not_read_as_a_sub_item_marker():
    """`/db/SECT` numbers two rows `DB` and `User`.

    A permissive roman-numeral pattern matches `DB`, which would make a
    section-type divider row into a child of whatever preceded it.
    """

    assert not ex._is_number_subitem("DB")
    assert not ex._is_number_subitem("User")
    assert ex._is_number_subitem("c")
    assert ex._is_number_subitem("iii")


def test_a_key_the_server_disproves_is_renamed_before_the_duplicate_is_dropped():
    """`/db/TDME` gives `"SCALE"` to a Number row and an Array[Object] row.

    The parser suppresses a duplicate key in the same numbered scope, so the
    second row vanished without a trace and its four documented children
    attached to the scalar that remained - the section read as one field that
    was a number and also had members. Renaming has to happen while the row is
    still a row; afterwards there is only one field where the request has two.

    `aDATA` is not a guess. `GET /info/db/TDME` lists both properties, and the
    capture is in `schema/info-schemas.json`.
    """

    assert ex._corrected_key("/db/TDME", "SCALE", "Array [Object]") == "aDATA"
    assert ex._corrected_key("/db/TDME", "SCALE", "Number") == "SCALE"
    assert ex._corrected_key("/db/TDMT", "SCALE", "Array [Object]") == "SCALE"


def test_a_renamed_key_carries_its_defect_record_into_the_draft(tmp_path: Path):
    """The rename is only half of it; the reason has to travel with it.

    A manual re-sync that reinstates the table's key has to argue with a
    `manualDefects` entry, rather than silently winning.
    """

    correction = ex._MANUAL_KEY_CORRECTIONS["/db/TDME"][("SCALE",)]

    assert correction.key == "aDATA"
    assert "/info/db/TDME" in correction.actual
    assert "schema/info-schemas.json" in correction.evidence
    assert "MD-13" in correction.evidence


def test_the_manuals_create_only_is_read_as_a_requiredness_not_dropped():
    """`Create Only` is the sibling of `Get Only` and was going nowhere.

    Both are the Required column naming a *method scope* rather than a
    requiredness, and `Get Only` has always mapped to `read_only`. `Create
    Only` fell through to the unrecognised-value note, so `/db/SECT` and
    `/db/SPFC` each carried an open question instead of the claim the manual
    actually makes.
    """

    assert ex._normalize_requirement("Create Only") == ("create_only", None, None)
    assert ex._normalize_requirement("create-only") == ("create_only", None, None)
    assert ex._normalize_requirement("Get Only") == ("read_only", None, None)


def test_create_only_records_the_manuals_claim_and_not_the_products_behaviour():
    """The manual uses this value twice and the product honours it once.

    Measured 2026-09-03: `/db/SECT` matches the cell exactly, `/db/SPFC` does
    not - `CALC_OPT: true` on a PUT rebuilds its spectrum. If `create_only`
    ever came to mean "the server ignores this on PUT", the contract would be
    asserting something false about one of the only two endpoints that use it.
    So the correction lives beside the value, and this test is what keeps the
    pair together.
    """

    assert "/db/SPFC" in ex._MANUAL_REQUIREDNESS_CORRECTIONS
    entries = ex._MANUAL_REQUIREDNESS_CORRECTIONS["/db/SPFC"]["CALC_OPT"]
    kinds = [entry.describes for entry in entries]

    assert "requiredness" in kinds
    assert any("honoured on PUT" in entry.actual for entry in entries)
    assert all("MD-15" in entry.evidence for entry in entries)
    assert "/db/SECT" not in ex._MANUAL_REQUIREDNESS_CORRECTIONS


def test_a_measured_requiredness_correction_names_the_cell_it_disproves():
    """`/db/PRES`'s row is wrong twice over, and they are different claims.

    `Optional` and a default of `"NORMAL"` are two statements; the run that
    disproved them refused the field's absence *and* the value it names. A
    single defect record would have to pick one, and a reader would then have
    the other reinstated by the next manual sync.
    """

    entries = ex._MANUAL_REQUIREDNESS_CORRECTIONS["/db/PRES"]["DIRECTION"]
    kinds = {entry.describes for entry in entries}

    assert kinds == {"requiredness", "default"}
    assert all("live_verification_notes" in entry.evidence for entry in entries)


def test_every_measured_correction_describes_a_kind_the_schema_accepts():
    """`describes` is a closed enum in the contract schema.

    These records are written straight into a draft, so a value the schema
    does not know would only surface as a validation failure on whichever
    endpoint happened to be promoted next.
    """

    schema = json.loads(
        (ROOT / "contracts" / "schema" / "endpoint-contract.schema.json").read_text(
            encoding="utf-8"
        )
    )
    allowed = set(
        schema["properties"]["manualDefects"]["items"]["properties"]["describes"]["enum"]
    )

    for endpoint, fields in ex._MANUAL_REQUIREDNESS_CORRECTIONS.items():
        for key, entries in fields.items():
            for entry in entries:
                assert entry.describes in allowed, f"{endpoint} {key}: {entry.describes}"


def _table(heading: str, *keys: str) -> "ex.ParsedTable":
    """A supplementary table under `heading`, documenting `keys`."""

    return ex.ParsedTable(
        heading=heading,
        line=1,
        fields=[_field("1", key, "String") for key in keys],
        missing_columns=[],
    )


def test_a_colon_inside_a_documented_code_name_is_not_a_discriminator():
    """`/db/TDME` heads two tables with lists of `CODENAME` values.

    One of them is `INDIA(IRC:112-2011)`, and the colon inside that name has
    the shape of a gate: field `IRC`, value `112-2011`. There is no `IRC` field
    anywhere in the endpoint, and the real discriminator - `CODENAME` - never
    appears in the `FIELD = VALUE` form the parser looks for. The contract that
    came out said an endpoint branches on a field it does not have.
    """

    base = _table("common", "NAME", "TYPE", "CODENAME", "STRENGTH")
    branch = _table("`CEB-FIP(1990)` · `INDIA(IRC:112-2011)` 전용 추가 필드", "iCTYPE")

    assert ex._explicit_variants([base, branch]) == []


def test_a_gate_in_parentheses_still_counts_when_the_field_is_real():
    """The rule has to be about the field, not about the punctuation.

    `/db/MVLDch` and `/db/MVLDpl` head four tables
    `Moving Load Optimization(bAUTO_OPTIMIZE=true)` - parentheses attached to a
    word, exactly like `INDIA(IRC:...)`. Reading the shape rather than the
    field would have thrown these four away to catch the two.
    """

    base = _table("common", "NAME", "bAUTO_OPTIMIZE")
    branch = _table("Moving Load Optimization(bAUTO_OPTIMIZE=true)", "OPT_FACTOR")

    variants = ex._explicit_variants([base, branch])

    assert [v.conditions for v in variants] == [(("bAUTO_OPTIMIZE", (True,)),)]


def test_a_gate_may_name_a_field_only_a_branch_table_documents():
    """The discriminator is not always in the first table.

    Checking only the base table would drop a legitimate variant whose
    selector the manual introduces alongside the branch it selects, so the
    check spans every table in the section.
    """

    base = _table("common", "NAME")
    branch = _table('Sub-branch (`MODE` = "FAST")', "MODE", "SPEED")

    variants = ex._explicit_variants([base, branch])

    assert [v.conditions for v in variants] == [(("MODE", ("FAST",)),)]


def test_a_hash_comment_in_a_code_block_is_not_a_table_heading(tmp_path: Path):
    """`# Canada 표준 차량 ...` sits inside a Python example, not above a table.

    ch08 alternates a country's parameter table with a runnable example, and
    the example's first line is a comment naming that country. Reading it as a
    Markdown heading gave five tables the heading of the *previous* country -
    the Australia table was labelled Canada - so a contract drafted from one
    would have cited the wrong article for the right fields.
    """

    path = tmp_path / "99_DB_Fenced.md"
    path.write_text(
        '''## 1. `/db/FENCED` -- fenced comment

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Name | `NAME` | String | - | Required |

### First country

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | First factor | `FIRST` | Number | - | Required |

```python
# An example for the first country
call({"FIRST": 1})
```

### Second country

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Second factor | `SECOND` | Number | - | Required |
''',
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]
    headings = [table.heading for table in section.tables]

    assert headings == ["Specifications", "First country", "Second country"]
    assert "An example for the first country" not in headings


def test_a_bold_label_followed_only_by_its_source_link_still_labels_the_table(
    tmp_path: Path,
):
    """ch08 labels nine objects `**VEH_XX (Country, gate)** - [원문](url)`.

    Requiring the line to end at the closing `**` skipped every one, and the
    gate those labels state - `STANDARD_CODE: "AUSTRALIA"` - went with them.
    Measured across the manual, the trailing-link form appears five times and
    introduces a parameter table every time.
    """

    path = tmp_path / "99_DB_Labelled.md"
    path.write_text(
        '''## 1. `/db/LABELLED` -- labelled tables

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Standard code | `STANDARD_CODE` | String | - | Required |

**VEH_AU (Australia, `STANDARD_CODE: "AUSTRALIA"`)** - [source](https://example.invalid/1)

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Allowance | `DYN_LOAD_ALLOWANCE` | Number | 0 | Optional |
''',
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]

    assert section.tables[1].heading.startswith("VEH_AU (Australia")
    assert [v.conditions for v in section.variants] == [
        (("STANDARD_CODE", ("AUSTRALIA",)),)
    ]


def test_a_bold_label_keeps_a_trailing_product_qualifier_out_of_the_title(
    tmp_path: Path,
):
    """SPLC's two GEN-only labels end in italic product metadata."""
    path = tmp_path / "99_DB_ProductLabel.md"
    path.write_text(
        '''## 1. `/db/SPLC` -- labelled tables

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Name | `NAME` | String | - | Required |

**비소산 요소 설계 파라미터** *(GEN NX only)*

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 2 | Design | `bNDP` | Boolean | false | Optional |
''',
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]

    assert section.tables[1].heading == "비소산 요소 설계 파라미터"


def test_bold_prose_that_introduces_an_example_is_still_not_a_heading(tmp_path: Path):
    """The widened label must not start swallowing bold prose.

    The rule that keeps it narrow is unchanged: a bold line only becomes a
    heading when a parameter table follows it before the next heading, label or
    fence. A bold line introducing a code block does not.
    """

    path = tmp_path / "99_DB_Prose.md"
    path.write_text(
        '''## 1. `/db/PROSE` -- bold prose

### Specifications

| No. | Description | Key | Value Type | Default | Required |
|---|---|---|---|---|---|
| 1 | Name | `NAME` | String | - | Required |

**Request Example** - [source](https://example.invalid/2)

```python
call({"NAME": "x"})
```
''',
        encoding="utf-8",
    )

    section = ex.parse_chapter(path)[0]

    assert [table.heading for table in section.tables] == ["Specifications"]


def test_a_row_numbered_under_a_boolean_becomes_its_sibling_not_its_member():
    """`/db/SPLC` writes `30 bNDP` (Boolean) then `(1) NDP` (Number).

    `NDP` is the value that flag turns on. Retyping `bNDP` to an object to
    hold it resolves a contradiction between the Value Type column and the No.
    column by discarding one of them, and produces a payload shape - `{"bNDP":
    {"NDP": 1}}` - that no request example in the manual sends.
    """

    parent = _field("30", "bNDP", "Boolean")
    child = _field("(1)", "NDP", "Number")

    roots = ex._nest([parent, child])

    assert [f.key for f in roots] == ["bNDP", "NDP"]
    assert parent.type.lower() == "boolean"
    assert parent.properties == []
    assert any("cannot hold members" in note for note in child.notes)


def test_a_row_numbered_under_a_real_object_is_still_its_member():
    """The rule is about scalars, and must not touch ordinary nesting.

    `SECT_BEFORE` is an Object with twelve numbered members, and 365 fields
    across the manual are nested exactly this way.
    """

    parent = _field("3", "SECT_BEFORE", "Object")
    child = _field("(1)", "SHAPE", "String")

    roots = ex._nest([parent, child])

    assert [f.key for f in roots] == ["SECT_BEFORE"]
    assert [f.key for f in parent.properties] == ["SHAPE"]


def test_the_sibling_lands_beside_its_scalar_inside_a_shared_parent():
    """A scalar nested two deep keeps its orphan at its own level, not the root.

    Promoting the row all the way out would put a member of one object beside
    the request's top-level fields, which is the /db/BTMP failure in reverse.
    """

    grandparent = _field("4", "GROUP", "Object")
    parent = _field("4-1", "FLAG", "Boolean")
    child = _field("4-1-2", "VALUE", "Number")

    roots = ex._nest([grandparent, parent, child])

    assert [f.key for f in roots] == ["GROUP"]
    assert [f.key for f in grandparent.properties] == ["FLAG", "VALUE"]
    assert parent.properties == []


def test_a_reviewed_renesting_is_checked_by_name_rather_than_read_as_drift():
    """A `field_name` defect says the table's own paths are wrong.

    The base-field comparison has honoured that override since it was
    introduced; the variant comparison did not, so `/db/SECT` - whose four
    SECTTYPE tables number their rows against a table they are not in - looked
    like 30 separate drift failures for a correction that was the point of the
    contract. Comparing by name keeps type, requiredness and default checked,
    and still catches a field that simply vanished.
    """

    source = ROOT / "scripts" / "extract_contracts.py"
    body = source.read_text(encoding="utf-8")

    assert 'renested = "field_name" in overridden' in body
    assert body.count("key.rsplit(\".\", 1)[-1]") == 2


def test_the_seventh_settled_marker_is_the_sections_own_worked_payload():
    """A Request Example is the manual speaking in the wire's own grammar.

    It is the only thing that places `/db/SECT`'s variant fields, so a note
    citing one is a conclusion rather than a question - and promotion refuses a
    draft still carrying `# NOTE:`.
    """

    assert ex._note_marker("the section's Request Example places it under X") == "RESOLVED"
    assert ex._note_marker("somebody should work out where this goes") == "NOTE"


def test_a_declared_structural_destination_is_not_drift():
    """A heading that names where its rows go must not read as an invented field.

    The parser flattens every table in a section into one namespace, so it
    holds `LL_NAME` where a correct contract holds `COMMON.LL_NAME`. Comparing
    those as strings passes the flat shape the server refuses and fails the
    nested one it takes - which is what kept the four /db/LLAN* contracts flat.
    The exemption stays narrow: the leaf still has to be a name the manual's
    tables state.
    """
    from extract_contracts import _under_structural_destination

    manual = {"LL_NAME": object(), "WIDTH": object()}
    destinations = {"COMMON"}

    assert _under_structural_destination("COMMON", destinations, manual)
    assert _under_structural_destination("COMMON.LL_NAME", destinations, manual)
    # A member the manual never mentions is still reported.
    assert not _under_structural_destination("COMMON.INVENTED", destinations, manual)
    # And nothing outside a declared destination is exempt.
    assert not _under_structural_destination("LANE_ITEMS.ELEM", destinations, manual)


def test_a_structural_destination_accepts_names_from_the_sections_other_tables():
    """/db/MVLDpl states DEFAULT's members in LOAD_MODEL groups the draft does
    not merge, so the names are the section's without being `manual_fields`.

    The exemption widens to those names and no further: a member no table in
    the section names is still reported.
    """
    from extract_contracts import _under_structural_destination

    destinations = {"DEFAULT"}
    names = frozenset({"DEFAULT", "COMB_OPTION", "SUB_LOAD_DATAS", "LANE_NAMES"})
    assert not _under_structural_destination("DEFAULT.COMB_OPTION", destinations, {})
    assert _under_structural_destination("DEFAULT.COMB_OPTION", destinations, {}, names)
    assert _under_structural_destination("DEFAULT.SUB_LOAD_DATAS.LANE_NAMES", destinations, {}, names)
    assert not _under_structural_destination("DEFAULT.INVENTED", destinations, {}, names)
    assert not _under_structural_destination("AUTO_OPTIMIZE.COMB_OPTION", destinations, {}, names)
    assert _under_structural_destination("COMB_OPTION", {"<root>"}, {}, names)
    assert not _under_structural_destination("INVENTED", {"<root>"}, {}, names)
    assert _under_structural_destination("SUB_LOAD_DATAS.LANE_NAMES", {"<root>"}, {}, names)
    assert not _under_structural_destination("SUB_LOAD_DATAS.INVENTED", {"<root>"}, {}, names)
    assert not _under_structural_destination("COMB_OPTION", {"DEFAULT"}, {}, names)


def test_a_key_cell_naming_its_object_is_read_as_the_key():
    """/db/SPFC writes `SFI`(STR) and `PERIOD`(VAL); the name is SFI, PERIOD."""
    from extract_contracts import _KEY_WITH_OBJECT

    assert _KEY_WITH_OBJECT.sub("", "SFI(STR)") == "SFI"
    assert _KEY_WITH_OBJECT.sub("", "FUNDAMENTAL_PERIOD(VAL)") == "FUNDAMENTAL_PERIOD"
    assert _KEY_WITH_OBJECT.sub("", "R_") == "R_"
    assert _KEY_WITH_OBJECT.sub("", "Pi(x)") == "Pi(x)"


def test_a_branch_that_redeclares_its_destination_accounts_for_the_rows():
    """/db/MCON: two `TYPE=... 일 때 SLAVES[]` tables, kept as variants.

    Merged into the parent, the two tables made SLAVES[] demand all four keys
    of both. Kept as variants that redeclare SLAVES, each branch carries its
    own - and the check must then find the rows there, but only where a
    reviewed `note` says that placement was chosen.
    """
    from extract_contracts import _branch_destination_fields

    slaves = lambda *keys: {  # noqa: E731
        "key": "SLAVES", "type": "array", "properties": [{"key": k, "type": "number"} for k in keys],
    }
    contract = {
        "variants": [
            {"when": [{"path": "TYPE", "equals": "EX"}], "fields": [slaves("NODE_KEY", "COEFF")]},
            {"when": [{"path": "TYPE", "equals": "WD"}], "fields": [slaves("NODE_KEY", "WEIGHT")]},
        ],
        "extraction": {"structuralTables": [
            {"heading": "EX SLAVES[]", "line": 1, "paths": ["ITEMS.SLAVES"], "note": "kept as a branch"},
        ]},
    }
    found = _branch_destination_fields(contract)
    assert {"ITEMS.SLAVES", "ITEMS.SLAVES.NODE_KEY", "ITEMS.SLAVES.COEFF", "ITEMS.SLAVES.WEIGHT"} <= set(found)

    del contract["extraction"]["structuralTables"][0]["note"]
    assert _branch_destination_fields(contract) == {}


def test_a_dashed_parenthesised_number_is_a_second_level_row():
    """/db/SDIS numbers LRB's DX `(8)` and its members `(8)-i` to `(8)-iv`.

    Read as unnumbered, the four landed beside DX inside LRB rather than in it,
    which the merged SDIS contract would have reported as drift.
    """
    from extract_contracts import _NUMBER_PAREN_DASH_SUBITEM

    for number in ("(8)-i", "(8)-iv", "(12)-b"):
        assert _NUMBER_PAREN_DASH_SUBITEM.match(number), number
    for number in ("(8)", "8-1", "(8)a", "i"):
        assert not _NUMBER_PAREN_DASH_SUBITEM.match(number), number


def test_a_packed_key_cell_becomes_the_names_it_holds():
    """A Key cell can name several properties, and the parser returns one key.

    That is harmless while the cell only feeds a count, and wrong the moment
    the names are used as a waiver: `"bSD" / "iSDOPT" / "SDCONST"` recorded
    verbatim accounts for no field at all, and all three then read as names
    nobody has looked at. Only the three forms the manual actually uses are
    unpacked, and only for unmergedTables[].fieldNames.
    """
    from extract_contracts import _unpack_key_cell

    assert _unpack_key_cell('bSD" / "iSDOPT" / "SDCONST') == ["bSD", "iSDOPT", "SDCONST"]
    assert _unpack_key_cell('_3_LANE_FACTOR_1" ~ "_3_LANE_FACTOR_4') == [
        "_3_LANE_FACTOR_1", "_3_LANE_FACTOR_2", "_3_LANE_FACTOR_3", "_3_LANE_FACTOR_4",
    ]
    assert _unpack_key_cell("SFI(STR)") == ["SFI"]
    assert _unpack_key_cell('SEL_VEHICLE"(표준)/"SUB_TYPE"(User)') == [
        "SEL_VEHICLE", "SUB_TYPE",
    ]
    # An ordinary key is returned unchanged, quotes and all removed.
    assert _unpack_key_cell('"DYNA_FACTOR"') == ["DYNA_FACTOR"]
    assert _unpack_key_cell("NODE") == ["NODE"]
    # A range whose ends do not share a stem is not a range, and there is no
    # separator to fall back on, so the cell survives intact and stays visible
    # as the oddity it is rather than being guessed at.
    assert _unpack_key_cell('A1" ~ "B4') == ['A1" ~ "B4']


def test_a_repeated_parent_row_brings_its_members_into_the_existing_field():
    """/view/RESULTGRAPHIC's detail tables repeat the parent row table 1 lists.

    `TYPE_OF_DISPLAY.CONTOUR`'s table opens with the `CONTOUR` row table 1
    already placed under TYPE_OF_DISPLAY, then gives its members. Until
    2026-09-22 the repeat was recognised as the same field and its members
    were dropped with it, so the merge reported success and published ten
    empty objects.
    """
    listed = ex.ParsedField("CONTOUR", "Contour", "object", None, "optional", None)
    repeat = ex.ParsedField("CONTOUR", "Contour", "object", None, "optional", None)
    repeat.properties = [ex.ParsedField("OPT_CHECK", "Show", "boolean", None, "optional", False)]
    destination = [listed]

    assert ex._append_fields(destination, [repeat])
    assert [member.key for member in destination[0].properties] == ["OPT_CHECK"]

    clash = ex.ParsedField("CONTOUR", "Contour", "object", None, "optional", None)
    clash.properties = [ex.ParsedField("OPT_CHECK", "Show", "string", None, "optional", None)]
    assert not ex._append_fields(destination, [clash]), "a member declared two ways stays blocked"


def test_a_labelled_child_number_still_nests_its_row():
    """/db/FIBR numbers its colour row `(1) R/G/B` under FIMP_COLOR."""
    assert ex._NUMBER_CHILD.match("(1)")
    assert ex._NUMBER_CHILD.match("(1) R/G/B")
    assert not ex._NUMBER_CHILD.match("1")
    assert not ex._NUMBER_CHILD.match("(1)a")
