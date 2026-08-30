"""ScoreMax V6.3.0 universal mastery runtime foundation.

Feature-flagged descendant of V6.2.8.1 implementing the governed v0.8 / v1.2
universal mastery contract in parallel with the legacy mastery engine.

Design boundaries
-----------------
* Power House remains the academic authority. This module does not academically approve
  questions, sources, nodes, families, seeds, or exam profiles.
* The runtime separates Knowledge Node -> Claim Family -> Reasoning Seed -> Question
  Variant. Claim Family is the independent knowledge-mastery unit.
* QA_SANDBOX_ONLY evidence is partitioned from LIVE evidence and can never mutate the
  existing ScoreMax ``mastery_records`` table.
* The initial V6.3 release runs the universal engine in SHADOW/PILOT mode. It computes
  replayable states and recovery queues without rewriting historical legacy mastery.
* Content priority and full-exam execution priority remain separate channels.

Architecture reference: ScoreMax Universal Mastery Architecture v0.8, governance v1.2,
13 August 2026 (SM-001..SM-069).
"""
from __future__ import annotations

import hashlib
import json
import math
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import Any, Iterable, Mapping, Sequence

ARCHITECTURE_VERSION = "0.8"
GOVERNANCE_REFERENCE_VERSION = "1.2"
EVIDENCE_SCHEMA_VERSION = "UM-1"
DEFAULT_RULESET_VERSION = "UM-0.8-PILOT-1"
ENGINE_VERSION = "6.3.0"

ENV_LIVE = "LIVE"
ENV_QA = "QA_SANDBOX_ONLY"
VALID_ENVIRONMENTS = {ENV_LIVE, ENV_QA}

MASTERY_STATES = (
    "UNSEEN",
    "LEARNING",
    "PROVISIONALLY_MASTERED",
    "VERIFIED_MASTERED",
    "MAINTENANCE_DUE",
    "AT_RISK",
    "REOPENED",
)

ASSISTANCE_STATES = (
    "UNASSISTED",
    "NUDGE",
    "HINT",
    "FORMULA_REVEAL",
    "EXPLANATION",
    "SOLUTION_REPLAY",
)

CONFIDENCE_BANDS = ("CERTAIN", "FAIRLY_SURE", "UNSURE", "GUESSED", "")

ERROR_CODES = (
    "KNOWLEDGE_GAP",
    "MISCONCEPTION",
    "WRONG_PRINCIPLE_SELECTED",
    "PREREQUISITE_GAP",
    "DIAGRAM_FBD_ERROR",
    "VECTOR_DIRECTION_ERROR",
    "SIGN_ERROR",
    "FORMULA_RECALL_ERROR",
    "FORMULA_CONDITION_ERROR",
    "ALGEBRA_ERROR",
    "ARITHMETIC_ERROR",
    "UNIT_DIMENSION_ERROR",
    "QUESTION_READING_ERROR",
    "DISTRACTOR_TRAP",
    "TIME_PRESSURE_ERROR",
    "OVERCONFIDENT_GUESS",
    "CBT_OMR_EXECUTION_ERROR",
    "ANSWER_ENTRY_ERROR",
    "PACING_ERROR",
    "LATE_CHANGE_ERROR",
    "FATIGUE_ERROR",
    "UNKNOWN",
)

PURPOSES = (
    "KNOW_CHECK",
    "SUBJECT_MASTERY",
    "REASONING",
    "EXAM_BRIDGE",
    "EXAM",
    "RECOVERY",
    "RECONFIRMATION",
)

LAYERS = ("L1_KNOW", "L2_UNDERSTAND", "L3_REASON", "L4_APPLY", "L5_PERFORM", "L6_RETAIN")

DELIVERY_CONTEXTS = ("BLOCKED", "INTERLEAVED", "AUTHENTIC_EXAM", "RECOVERY", "RECONFIRMATION")

SYLLABUS_COMPATIBILITY = (
    "CURRENT_COMPATIBLE",
    "HISTORICAL_COMPATIBLE",
    "OUTSIDE_CURRENT_SYLLABUS",
    "SYLLABUS_NOVEL",
    "UNKNOWN",
)

MAPPING_ROLES = ("PRIMARY", "SECONDARY", "INCIDENTAL")

GATE_TYPES = ("REQUIRED_CORRECT", "MISCONCEPTION_GUARD", "HIGH_CONFIDENCE_WRONG", "REPEATED_WRONG")

DEFAULT_FAMILY_POLICY = {
    "min_distinct_routes": 2,
    "min_qualifying_weight": 1.0,
    "require_unseen_transfer": True,
    "verification_days": 90,
    "reopen_wrong_threshold": 2,
}

DEFAULT_NODE_POLICY = {
    "min_distinct_routes": 1,
    "min_qualifying_weight": 1.0,
    "require_unseen_transfer": False,
    "verification_days": 90,
    "reopen_wrong_threshold": 2,
}

DEFAULT_SEED_POLICY = {
    "min_distinct_routes": 1,
    "min_qualifying_weight": 1.0,
    "require_unseen_transfer": True,
    "verification_days": 75,
    "reopen_wrong_threshold": 2,
}

MIN_CONFIDENCE_CALIBRATION_SAMPLE = 12
MIN_RECOVERY_OBSERVATIONS = 5


def utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def checksum(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def safe_json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list, tuple, int, float, bool)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def text(value: Any) -> str:
    return str(value or "").strip()


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return text(value).lower() in {"1", "true", "yes", "y", "on", "enabled", "active"}


def _today(as_of: date | datetime | str | None = None) -> date:
    if as_of is None:
        return datetime.utcnow().date()
    if isinstance(as_of, datetime):
        return as_of.date()
    if isinstance(as_of, date):
        return as_of
    raw = text(as_of).replace("Z", "")
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        return date.fromisoformat(raw[:10])


def _iso_date(value: date | datetime) -> str:
    return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()


def _learner_key(student_id: Any) -> str:
    raw = text(student_id)
    if raw.startswith(("USER:", "QA:")):
        return raw
    return f"USER:{raw}"


def _environment(value: str) -> str:
    value = text(value).upper() or ENV_LIVE
    if value not in VALID_ENVIRONMENTS:
        raise ValueError(f"Unsupported evidence environment: {value}")
    return value


def _state_rank(state: str) -> int:
    order = {
        "UNSEEN": 0,
        "LEARNING": 1,
        "PROVISIONALLY_MASTERED": 2,
        "VERIFIED_MASTERED": 3,
        "MAINTENANCE_DUE": 3,
        "AT_RISK": 2,
        "REOPENED": 1,
    }
    return order.get(text(state).upper(), 0)


def init_schema(c) -> None:
    """Create the V6.3 universal runtime schema without altering legacy mastery data."""
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS universal_architecture_versions(
          architecture_version TEXT PRIMARY KEY,
          governance_reference_version TEXT NOT NULL,
          engine_version TEXT NOT NULL,
          ruleset_version TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'PILOT',
          requirement_range TEXT NOT NULL DEFAULT 'SM-001..SM-069',
          requirement_count INTEGER NOT NULL DEFAULT 69,
          p0_count INTEGER NOT NULL DEFAULT 39,
          created_at TEXT NOT NULL,
          checksum TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_feature_flags(
          id INTEGER PRIMARY KEY,
          feature_code TEXT NOT NULL,
          scope_type TEXT NOT NULL DEFAULT 'GLOBAL',
          scope_key TEXT NOT NULL DEFAULT '*',
          enabled INTEGER NOT NULL DEFAULT 0,
          mode TEXT NOT NULL DEFAULT 'SHADOW',
          configuration_json TEXT NOT NULL DEFAULT '{}',
          ruleset_version TEXT NOT NULL DEFAULT 'UM-0.8-PILOT-1',
          updated_at TEXT NOT NULL,
          UNIQUE(feature_code,scope_type,scope_key));

        CREATE TABLE IF NOT EXISTS universal_market_adapters(
          adapter_id TEXT PRIMARY KEY,
          market TEXT NOT NULL,
          product_scope TEXT NOT NULL DEFAULT '',
          architecture_version TEXT NOT NULL,
          adapter_version TEXT NOT NULL,
          required_authority_roles_json TEXT NOT NULL DEFAULT '[]',
          labels_json TEXT NOT NULL DEFAULT '{}',
          status TEXT NOT NULL DEFAULT 'PILOT',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_market_authority_sources(
          id INTEGER PRIMARY KEY,
          adapter_id TEXT NOT NULL,
          authority_role TEXT NOT NULL,
          authority_name TEXT NOT NULL,
          source_id TEXT NOT NULL,
          source_version TEXT NOT NULL,
          source_locator TEXT NOT NULL DEFAULT '',
          source_checksum TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'UNRESOLVED',
          effective_from TEXT NOT NULL DEFAULT '',
          effective_to TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          UNIQUE(adapter_id,authority_role,source_id,source_version));

        CREATE TABLE IF NOT EXISTS universal_source_documents(
          source_id TEXT PRIMARY KEY,
          authority_role TEXT NOT NULL DEFAULT '',
          authority_name TEXT NOT NULL DEFAULT '',
          market TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL,
          version TEXT NOT NULL DEFAULT '',
          file_hash TEXT NOT NULL DEFAULT '',
          rights_status TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'UNRESOLVED',
          created_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_source_locators(
          locator_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL,
          locator_type TEXT NOT NULL DEFAULT 'SECTION',
          locator_value TEXT NOT NULL,
          payload_type TEXT NOT NULL DEFAULT 'TEXT',
          checksum TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_claim_families(
          claim_family_id TEXT PRIMARY KEY,
          market_scope TEXT NOT NULL DEFAULT 'UNIVERSAL',
          programme TEXT NOT NULL DEFAULT '',
          subject TEXT NOT NULL,
          chapter TEXT NOT NULL DEFAULT '',
          unit TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL,
          subject_role TEXT NOT NULL DEFAULT 'CORE',
          exam_role TEXT NOT NULL DEFAULT 'ELIGIBLE',
          independent_weight REAL NOT NULL DEFAULT 1.0,
          closure_policy_json TEXT NOT NULL DEFAULT '{}',
          source_id TEXT NOT NULL DEFAULT '',
          source_locator_id TEXT NOT NULL DEFAULT '',
          syllabus_compatibility TEXT NOT NULL DEFAULT 'CURRENT_COMPATIBLE',
          version TEXT NOT NULL DEFAULT '1',
          status TEXT NOT NULL DEFAULT 'CANDIDATE',
          environment TEXT NOT NULL DEFAULT 'LIVE',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_knowledge_nodes(
          knowledge_node_id TEXT PRIMARY KEY,
          claim_family_id TEXT NOT NULL,
          market_scope TEXT NOT NULL DEFAULT 'UNIVERSAL',
          programme TEXT NOT NULL DEFAULT '',
          subject TEXT NOT NULL,
          chapter TEXT NOT NULL DEFAULT '',
          unit TEXT NOT NULL DEFAULT '',
          claim TEXT NOT NULL,
          source_role TEXT NOT NULL DEFAULT 'DIRECT',
          depth TEXT NOT NULL DEFAULT 'K1',
          exam_mastery_eligible INTEGER NOT NULL DEFAULT 1,
          source_id TEXT NOT NULL DEFAULT '',
          source_locator_id TEXT NOT NULL DEFAULT '',
          version TEXT NOT NULL DEFAULT '1',
          status TEXT NOT NULL DEFAULT 'CANDIDATE',
          environment TEXT NOT NULL DEFAULT 'LIVE',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_reasoning_seeds(
          reasoning_seed_id TEXT PRIMARY KEY,
          market_scope TEXT NOT NULL DEFAULT 'UNIVERSAL',
          programme TEXT NOT NULL DEFAULT '',
          subject TEXT NOT NULL,
          chapter TEXT NOT NULL DEFAULT '',
          unit TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL,
          decisive_operation TEXT NOT NULL,
          seed_type TEXT NOT NULL DEFAULT 'PRIMITIVE',
          common_complexity TEXT NOT NULL DEFAULT '',
          independent_weight REAL NOT NULL DEFAULT 1.0,
          parent_seed_ids_json TEXT NOT NULL DEFAULT '[]',
          source_id TEXT NOT NULL DEFAULT '',
          version TEXT NOT NULL DEFAULT '1',
          status TEXT NOT NULL DEFAULT 'CANDIDATE',
          environment TEXT NOT NULL DEFAULT 'LIVE',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_node_seed_map(
          id INTEGER PRIMARY KEY,
          knowledge_node_id TEXT NOT NULL,
          reasoning_seed_id TEXT NOT NULL,
          relation_type TEXT NOT NULL DEFAULT 'SUPPORTS',
          mapping_role TEXT NOT NULL DEFAULT 'SECONDARY',
          governance_status TEXT NOT NULL DEFAULT 'CANDIDATE',
          version TEXT NOT NULL DEFAULT '1',
          UNIQUE(knowledge_node_id,reasoning_seed_id,relation_type));

        CREATE TABLE IF NOT EXISTS universal_claim_family_gates(
          gate_id TEXT PRIMARY KEY,
          claim_family_id TEXT NOT NULL,
          knowledge_node_id TEXT NOT NULL,
          gate_type TEXT NOT NULL,
          trigger_json TEXT NOT NULL DEFAULT '{}',
          closure_effect TEXT NOT NULL DEFAULT 'BLOCK',
          required INTEGER NOT NULL DEFAULT 1,
          version TEXT NOT NULL DEFAULT '1',
          status TEXT NOT NULL DEFAULT 'ACTIVE',
          environment TEXT NOT NULL DEFAULT 'LIVE',
          created_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_prerequisite_edges(
          prerequisite_edge_id TEXT PRIMARY KEY,
          from_entity_type TEXT NOT NULL,
          from_entity_id TEXT NOT NULL,
          to_entity_type TEXT NOT NULL,
          to_entity_id TEXT NOT NULL,
          edge_type TEXT NOT NULL DEFAULT 'PREREQUISITE',
          strength TEXT NOT NULL DEFAULT 'MEDIUM',
          source_id TEXT NOT NULL DEFAULT '',
          source_locator_id TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'CANDIDATE',
          environment TEXT NOT NULL DEFAULT 'LIVE',
          created_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_question_architecture(
          architecture_question_id TEXT PRIMARY KEY,
          question_db_id INTEGER,
          external_question_id TEXT NOT NULL DEFAULT '',
          purpose TEXT NOT NULL DEFAULT 'SUBJECT_MASTERY',
          architecture_layer TEXT NOT NULL DEFAULT 'L2_UNDERSTAND',
          pedagogical_type TEXT NOT NULL DEFAULT '',
          authentic_exam_formats_json TEXT NOT NULL DEFAULT '[]',
          independent_mastery_weight REAL NOT NULL DEFAULT 0.0,
          parent_seed_id TEXT NOT NULL DEFAULT '',
          dependency_type TEXT NOT NULL DEFAULT 'DEPENDENT',
          transfer_level TEXT NOT NULL DEFAULT 'NEAR_COPY',
          surface_distance REAL NOT NULL DEFAULT 0.0,
          delivery_context TEXT NOT NULL DEFAULT 'BLOCKED',
          confidence_required INTEGER NOT NULL DEFAULT 0,
          evidence_validity TEXT NOT NULL DEFAULT 'VALID_IF_GOVERNED',
          source_role TEXT NOT NULL DEFAULT 'DIRECT',
          exam_mastery_eligible INTEGER NOT NULL DEFAULT 1,
          environment TEXT NOT NULL DEFAULT 'LIVE',
          version TEXT NOT NULL DEFAULT '1',
          status TEXT NOT NULL DEFAULT 'CANDIDATE',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(question_db_id));

        CREATE TABLE IF NOT EXISTS universal_question_node_map(
          id INTEGER PRIMARY KEY,
          architecture_question_id TEXT NOT NULL,
          knowledge_node_id TEXT NOT NULL,
          mapping_role TEXT NOT NULL DEFAULT 'PRIMARY',
          evidence_weight REAL NOT NULL DEFAULT 1.0,
          UNIQUE(architecture_question_id,knowledge_node_id));

        CREATE TABLE IF NOT EXISTS universal_question_family_map(
          id INTEGER PRIMARY KEY,
          architecture_question_id TEXT NOT NULL,
          claim_family_id TEXT NOT NULL,
          mapping_role TEXT NOT NULL DEFAULT 'PRIMARY',
          evidence_weight REAL NOT NULL DEFAULT 1.0,
          UNIQUE(architecture_question_id,claim_family_id));

        CREATE TABLE IF NOT EXISTS universal_question_seed_map(
          id INTEGER PRIMARY KEY,
          architecture_question_id TEXT NOT NULL,
          reasoning_seed_id TEXT NOT NULL,
          mapping_role TEXT NOT NULL DEFAULT 'PRIMARY',
          evidence_weight REAL NOT NULL DEFAULT 1.0,
          UNIQUE(architecture_question_id,reasoning_seed_id));

        CREATE TABLE IF NOT EXISTS universal_exam_rule_sets(
          exam_rule_set_id TEXT PRIMARY KEY,
          adapter_id TEXT NOT NULL,
          market TEXT NOT NULL,
          exam_code TEXT NOT NULL,
          exam_name TEXT NOT NULL,
          exam_year INTEGER NOT NULL,
          authority_name TEXT NOT NULL,
          authority_source_id TEXT NOT NULL DEFAULT '',
          source_version TEXT NOT NULL DEFAULT '',
          effective_from TEXT NOT NULL DEFAULT '',
          effective_to TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'ACTIVE',
          rule_version TEXT NOT NULL DEFAULT '1',
          created_at TEXT NOT NULL,
          UNIQUE(market,exam_code,exam_year,rule_version));

        CREATE TABLE IF NOT EXISTS universal_exam_format_rules(
          exam_format_rule_id TEXT PRIMARY KEY,
          exam_rule_set_id TEXT NOT NULL,
          format_code TEXT NOT NULL,
          section_code TEXT NOT NULL DEFAULT '',
          correct_marks REAL NOT NULL,
          wrong_marks REAL NOT NULL,
          blank_marks REAL NOT NULL DEFAULT 0,
          duration_seconds INTEGER NOT NULL DEFAULT 0,
          answer_mode TEXT NOT NULL DEFAULT 'SINGLE_CHOICE',
          rounding_policy_json TEXT NOT NULL DEFAULT '{}',
          anomaly_policy_json TEXT NOT NULL DEFAULT '{}',
          authentic INTEGER NOT NULL DEFAULT 1,
          status TEXT NOT NULL DEFAULT 'ACTIVE',
          created_at TEXT NOT NULL,
          UNIQUE(exam_rule_set_id,format_code,section_code));

        CREATE TABLE IF NOT EXISTS universal_exam_seed_profiles(
          exam_seed_profile_id TEXT PRIMARY KEY,
          reasoning_seed_id TEXT NOT NULL,
          exam_rule_set_id TEXT NOT NULL,
          authentic_formats_json TEXT NOT NULL DEFAULT '[]',
          difficulty_band TEXT NOT NULL DEFAULT '',
          target_time_seconds INTEGER NOT NULL DEFAULT 0,
          time_target_status TEXT NOT NULL DEFAULT 'INTERNAL',
          mastery_policy_json TEXT NOT NULL DEFAULT '{}',
          version TEXT NOT NULL DEFAULT '1',
          status TEXT NOT NULL DEFAULT 'CANDIDATE',
          UNIQUE(reasoning_seed_id,exam_rule_set_id,version));

        CREATE TABLE IF NOT EXISTS universal_response_events(
          response_event_id TEXT PRIMARY KEY,
          learner_key TEXT NOT NULL,
          architecture_question_id TEXT NOT NULL,
          question_db_id INTEGER,
          attempt_id INTEGER,
          assessment_session_id INTEGER,
          response_text TEXT NOT NULL DEFAULT '',
          is_correct INTEGER NOT NULL DEFAULT 0,
          marks_awarded REAL NOT NULL DEFAULT 0,
          response_started_at TEXT NOT NULL DEFAULT '',
          submitted_at TEXT NOT NULL,
          active_duration_seconds INTEGER NOT NULL DEFAULT 0,
          confidence_band TEXT NOT NULL DEFAULT '',
          assistance_state TEXT NOT NULL DEFAULT 'UNASSISTED',
          attempt_state TEXT NOT NULL DEFAULT 'ATTEMPTED',
          delivery_context TEXT NOT NULL DEFAULT 'BLOCKED',
          exam_rule_set_id TEXT NOT NULL DEFAULT '',
          exam_format_code TEXT NOT NULL DEFAULT '',
          evidence_context TEXT NOT NULL DEFAULT 'BLOCKED',
          transfer_level TEXT NOT NULL DEFAULT 'NEAR_COPY',
          environment TEXT NOT NULL DEFAULT 'LIVE',
          evidence_validity TEXT NOT NULL DEFAULT 'VALID',
          evidence_schema_version TEXT NOT NULL,
          ruleset_version TEXT NOT NULL,
          payload_checksum TEXT NOT NULL,
          created_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_assistance_events(
          assistance_event_id TEXT PRIMARY KEY,
          response_event_id TEXT NOT NULL,
          assistance_type TEXT NOT NULL,
          occurred_at TEXT NOT NULL,
          metadata_json TEXT NOT NULL DEFAULT '{}');

        CREATE TABLE IF NOT EXISTS universal_error_events(
          error_event_id TEXT PRIMARY KEY,
          response_event_id TEXT NOT NULL,
          learner_key TEXT NOT NULL,
          primary_error TEXT NOT NULL,
          secondary_error TEXT NOT NULL DEFAULT '',
          diagnostic_method TEXT NOT NULL DEFAULT 'ITEM_SIGNAL',
          diagnosis_confidence TEXT NOT NULL DEFAULT 'LOW',
          misconception_id TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_exam_item_transitions(
          transition_id TEXT PRIMARY KEY,
          learner_key TEXT NOT NULL,
          attempt_id INTEGER,
          architecture_question_id TEXT NOT NULL,
          transition_type TEXT NOT NULL,
          old_response TEXT NOT NULL DEFAULT '',
          new_response TEXT NOT NULL DEFAULT '',
          occurred_at TEXT NOT NULL,
          environment TEXT NOT NULL DEFAULT 'LIVE');

        CREATE TABLE IF NOT EXISTS universal_node_evidence(
          id INTEGER PRIMARY KEY,
          learner_key TEXT NOT NULL,
          knowledge_node_id TEXT NOT NULL,
          response_event_id TEXT NOT NULL,
          independence_key TEXT NOT NULL,
          is_correct INTEGER NOT NULL,
          qualifying_weight REAL NOT NULL DEFAULT 0,
          transfer_qualifies INTEGER NOT NULL DEFAULT 0,
          evidence_role TEXT NOT NULL DEFAULT 'PRIMARY',
          environment TEXT NOT NULL DEFAULT 'LIVE',
          created_at TEXT NOT NULL,
          UNIQUE(learner_key,knowledge_node_id,response_event_id,environment));

        CREATE TABLE IF NOT EXISTS universal_family_evidence(
          id INTEGER PRIMARY KEY,
          learner_key TEXT NOT NULL,
          claim_family_id TEXT NOT NULL,
          response_event_id TEXT NOT NULL,
          independence_key TEXT NOT NULL,
          is_correct INTEGER NOT NULL,
          qualifying_weight REAL NOT NULL DEFAULT 0,
          transfer_qualifies INTEGER NOT NULL DEFAULT 0,
          evidence_role TEXT NOT NULL DEFAULT 'PRIMARY',
          environment TEXT NOT NULL DEFAULT 'LIVE',
          created_at TEXT NOT NULL,
          UNIQUE(learner_key,claim_family_id,response_event_id,environment));

        CREATE TABLE IF NOT EXISTS universal_seed_evidence(
          id INTEGER PRIMARY KEY,
          learner_key TEXT NOT NULL,
          reasoning_seed_id TEXT NOT NULL,
          response_event_id TEXT NOT NULL,
          independence_key TEXT NOT NULL,
          is_correct INTEGER NOT NULL,
          qualifying_weight REAL NOT NULL DEFAULT 0,
          transfer_qualifies INTEGER NOT NULL DEFAULT 0,
          evidence_role TEXT NOT NULL DEFAULT 'PRIMARY',
          environment TEXT NOT NULL DEFAULT 'LIVE',
          created_at TEXT NOT NULL,
          UNIQUE(learner_key,reasoning_seed_id,response_event_id,environment));

        CREATE TABLE IF NOT EXISTS universal_learner_node_state(
          learner_key TEXT NOT NULL,
          knowledge_node_id TEXT NOT NULL,
          environment TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'UNSEEN',
          evidence_confidence TEXT NOT NULL DEFAULT 'LOW',
          last_evidence_at TEXT NOT NULL DEFAULT '',
          last_verified_at TEXT NOT NULL DEFAULT '',
          maintenance_due_at TEXT NOT NULL DEFAULT '',
          reopen_reason TEXT NOT NULL DEFAULT '',
          retention_risk TEXT NOT NULL DEFAULT 'LOW',
          ruleset_version TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(learner_key,knowledge_node_id,environment));

        CREATE TABLE IF NOT EXISTS universal_learner_family_state(
          learner_key TEXT NOT NULL,
          claim_family_id TEXT NOT NULL,
          environment TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'UNSEEN',
          evidence_confidence TEXT NOT NULL DEFAULT 'LOW',
          last_evidence_at TEXT NOT NULL DEFAULT '',
          last_verified_at TEXT NOT NULL DEFAULT '',
          maintenance_due_at TEXT NOT NULL DEFAULT '',
          reopen_reason TEXT NOT NULL DEFAULT '',
          gate_status_json TEXT NOT NULL DEFAULT '{}',
          retention_risk TEXT NOT NULL DEFAULT 'LOW',
          ruleset_version TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(learner_key,claim_family_id,environment));

        CREATE TABLE IF NOT EXISTS universal_learner_seed_state(
          learner_key TEXT NOT NULL,
          reasoning_seed_id TEXT NOT NULL,
          environment TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'UNSEEN',
          evidence_confidence TEXT NOT NULL DEFAULT 'LOW',
          last_evidence_at TEXT NOT NULL DEFAULT '',
          last_verified_at TEXT NOT NULL DEFAULT '',
          maintenance_due_at TEXT NOT NULL DEFAULT '',
          reopen_reason TEXT NOT NULL DEFAULT '',
          retention_risk TEXT NOT NULL DEFAULT 'LOW',
          ruleset_version TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(learner_key,reasoning_seed_id,environment));

        CREATE TABLE IF NOT EXISTS universal_learner_exam_seed_state(
          learner_key TEXT NOT NULL,
          reasoning_seed_id TEXT NOT NULL,
          exam_rule_set_id TEXT NOT NULL,
          environment TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'UNSEEN',
          readiness_score REAL,
          fluency_state TEXT NOT NULL DEFAULT 'UNASSESSED',
          evidence_count INTEGER NOT NULL DEFAULT 0,
          last_verified_at TEXT NOT NULL DEFAULT '',
          ruleset_version TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(learner_key,reasoning_seed_id,exam_rule_set_id,environment));

        CREATE TABLE IF NOT EXISTS universal_mastery_state_history(
          history_id TEXT PRIMARY KEY,
          learner_key TEXT NOT NULL,
          entity_type TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          environment TEXT NOT NULL,
          old_state TEXT NOT NULL DEFAULT '',
          new_state TEXT NOT NULL,
          reason_code TEXT NOT NULL,
          response_event_id TEXT NOT NULL DEFAULT '',
          evidence_refs_json TEXT NOT NULL DEFAULT '[]',
          ruleset_version TEXT NOT NULL,
          created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_universal_mastery_history_lookup
          ON universal_mastery_state_history(learner_key,entity_type,entity_id,environment,new_state);

        CREATE TABLE IF NOT EXISTS universal_decision_log(
          decision_id TEXT PRIMARY KEY,
          learner_key TEXT NOT NULL DEFAULT '',
          decision_type TEXT NOT NULL,
          entity_type TEXT NOT NULL DEFAULT '',
          entity_id TEXT NOT NULL DEFAULT '',
          environment TEXT NOT NULL DEFAULT 'LIVE',
          input_json TEXT NOT NULL,
          input_checksum TEXT NOT NULL,
          output_json TEXT NOT NULL,
          ruleset_version TEXT NOT NULL,
          architecture_version TEXT NOT NULL,
          created_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_prerequisite_diagnostics(
          diagnostic_id TEXT PRIMARY KEY,
          learner_key TEXT NOT NULL,
          target_entity_type TEXT NOT NULL,
          target_entity_id TEXT NOT NULL,
          prerequisite_edge_id TEXT NOT NULL,
          result TEXT NOT NULL DEFAULT 'NEEDS_DIAGNOSTIC',
          diagnosis_confidence TEXT NOT NULL DEFAULT 'LOW',
          response_event_id TEXT NOT NULL DEFAULT '',
          environment TEXT NOT NULL DEFAULT 'LIVE',
          created_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_recovery_queue(
          recovery_id TEXT PRIMARY KEY,
          learner_key TEXT NOT NULL,
          entity_type TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          cause_code TEXT NOT NULL,
          cause_detail TEXT NOT NULL DEFAULT '',
          priority INTEGER NOT NULL DEFAULT 3,
          required_evidence TEXT NOT NULL DEFAULT 'UNASSISTED_TRANSFER',
          status TEXT NOT NULL DEFAULT 'OPEN',
          due_at TEXT NOT NULL DEFAULT '',
          environment TEXT NOT NULL DEFAULT 'LIVE',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(learner_key,entity_type,entity_id,cause_code,status,environment));

        CREATE TABLE IF NOT EXISTS universal_maintenance_queue(
          maintenance_id TEXT PRIMARY KEY,
          learner_key TEXT NOT NULL,
          entity_type TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          due_at TEXT NOT NULL,
          retention_risk TEXT NOT NULL DEFAULT 'LOW',
          reason TEXT NOT NULL DEFAULT 'EVIDENCE_FRESHNESS',
          status TEXT NOT NULL DEFAULT 'OPEN',
          environment TEXT NOT NULL DEFAULT 'LIVE',
          created_at TEXT NOT NULL,
          UNIQUE(learner_key,entity_type,entity_id,status,environment));

        CREATE TABLE IF NOT EXISTS universal_pyq_papers(
          pyq_paper_id TEXT PRIMARY KEY,
          exam_rule_set_id TEXT NOT NULL,
          exam_year INTEGER NOT NULL,
          source_id TEXT NOT NULL,
          compatibility TEXT NOT NULL DEFAULT 'UNKNOWN',
          evidence_grade TEXT NOT NULL DEFAULT 'OFFICIAL',
          status TEXT NOT NULL DEFAULT 'CANDIDATE',
          created_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_pyq_questions(
          pyq_question_id TEXT PRIMARY KEY,
          pyq_paper_id TEXT NOT NULL,
          marks REAL NOT NULL DEFAULT 1,
          format_code TEXT NOT NULL DEFAULT '',
          source_locator TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'CANDIDATE',
          created_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_pyq_seed_map(
          id INTEGER PRIMARY KEY,
          pyq_question_id TEXT NOT NULL,
          reasoning_seed_id TEXT NOT NULL,
          mapping_role TEXT NOT NULL DEFAULT 'PRIMARY',
          allocation_weight REAL NOT NULL DEFAULT 0,
          compatibility TEXT NOT NULL DEFAULT 'CURRENT_COMPATIBLE',
          confidence TEXT NOT NULL DEFAULT 'MEDIUM',
          UNIQUE(pyq_question_id,reasoning_seed_id));

        CREATE TABLE IF NOT EXISTS universal_score_opportunities(
          id INTEGER PRIMARY KEY,
          learner_key TEXT NOT NULL,
          exam_rule_set_id TEXT NOT NULL,
          reasoning_seed_id TEXT NOT NULL,
          historical_exam_weight REAL,
          historical_weight_confidence TEXT NOT NULL DEFAULT 'UNRESOLVED',
          syllabus_compatibility TEXT NOT NULL DEFAULT 'UNKNOWN',
          current_expected_score REAL,
          target_expected_score REAL,
          marks_at_risk REAL,
          unlock_factor REAL NOT NULL DEFAULT 1.0,
          retention_modifier REAL NOT NULL DEFAULT 1.0,
          repair_cost_index REAL NOT NULL DEFAULT 1.0,
          repair_cost_source_state TEXT NOT NULL DEFAULT 'CONTENT_COMPLEXITY',
          priority_score REAL,
          uncertainty TEXT NOT NULL DEFAULT 'HIGH',
          ruleset_version TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(learner_key,exam_rule_set_id,reasoning_seed_id));

        CREATE TABLE IF NOT EXISTS universal_learner_goal_policy(
          learner_key TEXT NOT NULL,
          exam_rule_set_id TEXT NOT NULL,
          goal_tier TEXT NOT NULL DEFAULT 'CORE',
          target_score_objective REAL,
          policy_version TEXT NOT NULL DEFAULT '1',
          rank_promise_prohibited INTEGER NOT NULL DEFAULT 1,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(learner_key,exam_rule_set_id));

        CREATE TABLE IF NOT EXISTS universal_repair_observations(
          id INTEGER PRIMARY KEY,
          learner_key TEXT NOT NULL,
          entity_type TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          complexity_band TEXT NOT NULL DEFAULT 'MEDIUM',
          observation_value REAL,
          qualifying INTEGER NOT NULL DEFAULT 0,
          observed_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_full_exam_execution_state(
          id INTEGER PRIMARY KEY,
          learner_key TEXT NOT NULL,
          exam_rule_set_id TEXT NOT NULL,
          attempt_id INTEGER,
          execution_component TEXT NOT NULL,
          estimated_loss REAL,
          evidence_confidence TEXT NOT NULL DEFAULT 'LOW',
          state TEXT NOT NULL DEFAULT 'OBSERVED',
          remediation_code TEXT NOT NULL DEFAULT '',
          content_seed_attribution REAL NOT NULL DEFAULT 0.0,
          ruleset_version TEXT NOT NULL,
          environment TEXT NOT NULL DEFAULT 'LIVE',
          created_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_strategy_calibration_state(
          learner_key TEXT NOT NULL,
          exam_rule_set_id TEXT NOT NULL,
          sample_count INTEGER NOT NULL DEFAULT 0,
          calibrated INTEGER NOT NULL DEFAULT 0,
          descriptive_only INTEGER NOT NULL DEFAULT 1,
          policy_version TEXT NOT NULL DEFAULT '1',
          updated_at TEXT NOT NULL,
          PRIMARY KEY(learner_key,exam_rule_set_id));

        CREATE TABLE IF NOT EXISTS universal_research_evidence(
          research_evidence_id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          source_reference TEXT NOT NULL DEFAULT '',
          evidence_role TEXT NOT NULL DEFAULT 'DESIGN_EVIDENCE',
          product_claim_status TEXT NOT NULL DEFAULT 'NOT_VALIDATED_SCOREMAX_OUTCOME',
          version TEXT NOT NULL DEFAULT '1',
          created_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS universal_growth_event_outbox(
          event_id TEXT PRIMARY KEY,
          event_type TEXT NOT NULL,
          user_key TEXT NOT NULL DEFAULT '',
          occurred_at TEXT NOT NULL,
          payload_json TEXT NOT NULL DEFAULT '{}',
          status TEXT NOT NULL DEFAULT 'PENDING',
          attempts INTEGER NOT NULL DEFAULT 0,
          last_error TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL);
        """
    )
    c.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_um_response_learner ON universal_response_events(learner_key,environment,created_at);
        CREATE INDEX IF NOT EXISTS idx_um_response_attempt ON universal_response_events(attempt_id);
        CREATE INDEX IF NOT EXISTS idx_um_node_evidence ON universal_node_evidence(learner_key,knowledge_node_id,environment,created_at);
        CREATE INDEX IF NOT EXISTS idx_um_family_evidence ON universal_family_evidence(learner_key,claim_family_id,environment,created_at);
        CREATE INDEX IF NOT EXISTS idx_um_seed_evidence ON universal_seed_evidence(learner_key,reasoning_seed_id,environment,created_at);
        CREATE INDEX IF NOT EXISTS idx_um_recovery_open ON universal_recovery_queue(learner_key,status,environment,priority);
        CREATE INDEX IF NOT EXISTS idx_um_maintenance_open ON universal_maintenance_queue(learner_key,status,environment,due_at);
        CREATE INDEX IF NOT EXISTS idx_um_growth_pending ON universal_growth_event_outbox(status,occurred_at);
        """
    )
    seed_defaults(c)


def seed_defaults(c) -> None:
    now = utcnow()
    arch_payload = {
        "architecture_version": ARCHITECTURE_VERSION,
        "governance_reference_version": GOVERNANCE_REFERENCE_VERSION,
        "engine_version": ENGINE_VERSION,
        "ruleset_version": DEFAULT_RULESET_VERSION,
        "requirements": "SM-001..SM-069",
        "requirement_count": 69,
        "p0_count": 39,
    }
    c.execute(
        """INSERT OR IGNORE INTO universal_architecture_versions(
          architecture_version,governance_reference_version,engine_version,ruleset_version,status,
          requirement_range,requirement_count,p0_count,created_at,checksum)
          VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (
            ARCHITECTURE_VERSION,
            GOVERNANCE_REFERENCE_VERSION,
            ENGINE_VERSION,
            DEFAULT_RULESET_VERSION,
            "PILOT",
            "SM-001..SM-069",
            69,
            39,
            now,
            checksum(arch_payload),
        ),
    )
    defaults = [
        ("universal_mastery_runtime", "GLOBAL", "*", 0, "SHADOW", {"legacy_mastery_authoritative": True}),
        ("universal_pakistan_retrospective", "MARKET", "PAKISTAN", 0, "SHADOW", {"prospective_evidence_only": True}),
        ("universal_india_pilot", "MARKET", "INDIA", 0, "SHADOW", {"pilot_only": True}),
        ("growth_event_outbox", "GLOBAL", "*", 1, "ACTIVE", {"delivery": "OUTBOX_ONLY"}),
    ]
    for code, scope_type, scope_key, enabled, mode, cfg in defaults:
        c.execute(
            """INSERT OR IGNORE INTO universal_feature_flags(
              feature_code,scope_type,scope_key,enabled,mode,configuration_json,ruleset_version,updated_at)
              VALUES(?,?,?,?,?,?,?,?)""",
            (code, scope_type, scope_key, enabled, mode, canonical_json(cfg), DEFAULT_RULESET_VERSION, now),
        )

    adapters = [
        (
            "PAKISTAN-FSC-MDCAT-v1",
            "PAKISTAN",
            "FSC_MDCAT",
            ["FEDERAL_STANDARD", "PROVINCIAL_CURRICULUM", "GOVERNING_TEXTBOOK", "EXAM_AUTHORITY"],
            {"school_product": "FSc", "entrance_exam": "MDCAT"},
        ),
        (
            "INDIA-NCERT-NEET-JEE-v1",
            "INDIA",
            "NCERT_NEET_JEE",
            ["GOVERNING_TEXTBOOK", "EXAM_SYLLABUS", "EXAM_AUTHORITY"],
            {"school_product": "Class XI/XII", "entrance_exams": ["NEET", "JEE_MAIN"]},
        ),
    ]
    for adapter_id, market, product, roles, labels in adapters:
        c.execute(
            """INSERT OR IGNORE INTO universal_market_adapters(
              adapter_id,market,product_scope,architecture_version,adapter_version,required_authority_roles_json,
              labels_json,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (adapter_id, market, product, ARCHITECTURE_VERSION, "1", canonical_json(roles), canonical_json(labels), "PILOT", now, now),
        )

    # Governed exam-rule examples from the v0.8 reference. These are explicit rule objects;
    # no shared negative-marking default exists.
    exam_sets = [
        ("PAK-MDCAT-2026-v1", "PAKISTAN-FSC-MDCAT-v1", "PAKISTAN", "MDCAT", "MDCAT 2026", 2026, "PM&DC", "ARCH-v0.8-PMDC", "2026", "MCQ", 1.0, 0.0, 0.0, "SINGLE_CHOICE"),
        ("IND-NEET-2026-v1", "INDIA-NCERT-NEET-JEE-v1", "INDIA", "NEET", "NEET UG 2026", 2026, "NTA/NMC", "ARCH-v0.8-NEET", "2026", "MCQ_SINGLE", 4.0, -1.0, 0.0, "SINGLE_CHOICE"),
        ("IND-JEE-2026-v1", "INDIA-NCERT-NEET-JEE-v1", "INDIA", "JEE_MAIN", "JEE Main 2026", 2026, "NTA", "ARCH-v0.8-JEE", "2026", "MCQ_SINGLE", 4.0, -1.0, 0.0, "SINGLE_CHOICE"),
    ]
    for rid, aid, market, code, name, year, authority, source_id, source_ver, fmt, correct, wrong, blank, answer_mode in exam_sets:
        c.execute(
            """INSERT OR IGNORE INTO universal_exam_rule_sets(
              exam_rule_set_id,adapter_id,market,exam_code,exam_name,exam_year,authority_name,authority_source_id,
              source_version,status,rule_version,created_at) VALUES(?,?,?,?,?,?,?,?,?,'ACTIVE','1',?)""",
            (rid, aid, market, code, name, year, authority, source_id, source_ver, now),
        )
        frid = f"{rid}:{fmt}"
        c.execute(
            """INSERT OR IGNORE INTO universal_exam_format_rules(
              exam_format_rule_id,exam_rule_set_id,format_code,correct_marks,wrong_marks,blank_marks,answer_mode,
              authentic,status,created_at) VALUES(?,?,?,?,?,?,?,1,'ACTIVE',?)""",
            (frid, rid, fmt, correct, wrong, blank, answer_mode, now),
        )
    # JEE numerical is format-specific and independently stored.
    c.execute(
        """INSERT OR IGNORE INTO universal_exam_format_rules(
          exam_format_rule_id,exam_rule_set_id,format_code,section_code,correct_marks,wrong_marks,blank_marks,
          answer_mode,authentic,status,created_at) VALUES(?,?,?,?,?,?,?,?,1,'ACTIVE',?)""",
        ("IND-JEE-2026-v1:NUMERICAL_VALUE", "IND-JEE-2026-v1", "NUMERICAL_VALUE", "B", 4.0, -1.0, 0.0, "NUMERICAL", now),
    )


def set_feature_flag(c, feature_code: str, enabled: bool, scope_type: str = "GLOBAL", scope_key: str = "*", mode: str = "SHADOW", configuration: Mapping[str, Any] | None = None) -> None:
    c.execute(
        """INSERT INTO universal_feature_flags(feature_code,scope_type,scope_key,enabled,mode,configuration_json,ruleset_version,updated_at)
          VALUES(?,?,?,?,?,?,?,?)
          ON CONFLICT(feature_code,scope_type,scope_key) DO UPDATE SET enabled=excluded.enabled,mode=excluded.mode,
          configuration_json=excluded.configuration_json,ruleset_version=excluded.ruleset_version,updated_at=excluded.updated_at""",
        (feature_code, scope_type.upper(), scope_key.upper(), 1 if enabled else 0, mode.upper(), canonical_json(configuration or {}), DEFAULT_RULESET_VERSION, utcnow()),
    )


def feature_enabled(c, feature_code: str, *, market: str = "", subject: str = "", learner_key: str = "") -> bool:
    checks = [
        ("LEARNER", text(learner_key).upper()),
        ("SUBJECT", text(subject).upper()),
        ("MARKET", text(market).upper()),
        ("GLOBAL", "*"),
    ]
    for scope_type, scope_key in checks:
        if not scope_key and scope_type != "GLOBAL":
            continue
        row = c.execute(
            "SELECT enabled FROM universal_feature_flags WHERE feature_code=? AND scope_type=? AND scope_key=?",
            (feature_code, scope_type, scope_key),
        ).fetchone()
        if row is not None:
            return bool(row["enabled"])
    return False


def register_authority_source(
    c,
    *,
    adapter_id: str,
    authority_role: str,
    authority_name: str,
    source_id: str,
    source_version: str,
    source_locator: str = "",
    source_checksum: str = "",
    status: str = "LOCKED",
    effective_from: str = "",
    effective_to: str = "",
) -> None:
    c.execute(
        """INSERT INTO universal_market_authority_sources(
          adapter_id,authority_role,authority_name,source_id,source_version,source_locator,source_checksum,status,effective_from,effective_to,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(adapter_id,authority_role,source_id,source_version) DO UPDATE SET
          authority_name=excluded.authority_name,source_locator=excluded.source_locator,source_checksum=excluded.source_checksum,
          status=excluded.status,effective_from=excluded.effective_from,effective_to=excluded.effective_to""",
        (adapter_id, authority_role, authority_name, source_id, source_version, source_locator, source_checksum, status, effective_from, effective_to, utcnow()),
    )


def market_release_ready(c, adapter_id: str) -> dict[str, Any]:
    adapter = c.execute("SELECT * FROM universal_market_adapters WHERE adapter_id=?", (adapter_id,)).fetchone()
    if not adapter:
        return {"ready": False, "reason": "UNKNOWN_ADAPTER", "missing_roles": []}
    required = safe_json(adapter["required_authority_roles_json"], [])
    locked = {
        r["authority_role"]
        for r in c.execute(
            "SELECT authority_role FROM universal_market_authority_sources WHERE adapter_id=? AND status='LOCKED'",
            (adapter_id,),
        ).fetchall()
    }
    missing = [role for role in required if role not in locked]
    return {"ready": not missing, "reason": "READY" if not missing else "MISSING_SOURCE_LOCK", "missing_roles": missing}


def upsert_claim_family(c, payload: Mapping[str, Any]) -> str:
    fid = text(payload.get("claim_family_id"))
    if not fid:
        raise ValueError("claim_family_id is required")
    policy = dict(DEFAULT_FAMILY_POLICY)
    policy.update(safe_json(payload.get("closure_policy"), {}) or {})
    compat = text(payload.get("syllabus_compatibility")).upper() or "CURRENT_COMPATIBLE"
    if compat not in SYLLABUS_COMPATIBILITY:
        raise ValueError(f"Unsupported syllabus compatibility: {compat}")
    env = _environment(text(payload.get("environment")) or ENV_LIVE)
    now = utcnow()
    c.execute(
        """INSERT INTO universal_claim_families(
          claim_family_id,market_scope,programme,subject,chapter,unit,title,subject_role,exam_role,independent_weight,
          closure_policy_json,source_id,source_locator_id,syllabus_compatibility,version,status,environment,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(claim_family_id) DO UPDATE SET market_scope=excluded.market_scope,programme=excluded.programme,
          subject=excluded.subject,chapter=excluded.chapter,unit=excluded.unit,title=excluded.title,subject_role=excluded.subject_role,
          exam_role=excluded.exam_role,independent_weight=excluded.independent_weight,closure_policy_json=excluded.closure_policy_json,
          source_id=excluded.source_id,source_locator_id=excluded.source_locator_id,syllabus_compatibility=excluded.syllabus_compatibility,
          version=excluded.version,status=excluded.status,environment=excluded.environment,updated_at=excluded.updated_at""",
        (
            fid,
            text(payload.get("market_scope")) or "UNIVERSAL",
            text(payload.get("programme")),
            text(payload.get("subject")),
            text(payload.get("chapter")),
            text(payload.get("unit")),
            text(payload.get("title")) or fid,
            text(payload.get("subject_role")) or "CORE",
            text(payload.get("exam_role")) or "ELIGIBLE",
            float(payload.get("independent_weight", 1.0) or 0),
            canonical_json(policy),
            text(payload.get("source_id")),
            text(payload.get("source_locator_id")),
            compat,
            text(payload.get("version")) or "1",
            text(payload.get("status")) or "CANDIDATE",
            env,
            now,
            now,
        ),
    )
    return fid


def upsert_knowledge_node(c, payload: Mapping[str, Any]) -> str:
    nid = text(payload.get("knowledge_node_id"))
    fid = text(payload.get("claim_family_id"))
    if not nid or not fid:
        raise ValueError("knowledge_node_id and claim_family_id are required")
    family = c.execute("SELECT 1 FROM universal_claim_families WHERE claim_family_id=?", (fid,)).fetchone()
    if not family:
        raise ValueError(f"Knowledge Node {nid} references unknown Claim Family {fid}")
    role = text(payload.get("source_role")).upper() or "DIRECT"
    if role not in {"DIRECT", "SUPPORTING", "SOURCE_ONLY"}:
        raise ValueError(f"Unsupported source_role: {role}")
    env = _environment(text(payload.get("environment")) or ENV_LIVE)
    now = utcnow()
    c.execute(
        """INSERT INTO universal_knowledge_nodes(
          knowledge_node_id,claim_family_id,market_scope,programme,subject,chapter,unit,claim,source_role,depth,
          exam_mastery_eligible,source_id,source_locator_id,version,status,environment,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(knowledge_node_id) DO UPDATE SET claim_family_id=excluded.claim_family_id,market_scope=excluded.market_scope,
          programme=excluded.programme,subject=excluded.subject,chapter=excluded.chapter,unit=excluded.unit,claim=excluded.claim,
          source_role=excluded.source_role,depth=excluded.depth,exam_mastery_eligible=excluded.exam_mastery_eligible,
          source_id=excluded.source_id,source_locator_id=excluded.source_locator_id,version=excluded.version,status=excluded.status,
          environment=excluded.environment,updated_at=excluded.updated_at""",
        (
            nid,
            fid,
            text(payload.get("market_scope")) or "UNIVERSAL",
            text(payload.get("programme")),
            text(payload.get("subject")),
            text(payload.get("chapter")),
            text(payload.get("unit")),
            text(payload.get("claim")) or nid,
            role,
            text(payload.get("depth")) or "K1",
            0 if role == "SOURCE_ONLY" else (1 if truthy(payload.get("exam_mastery_eligible", True)) else 0),
            text(payload.get("source_id")),
            text(payload.get("source_locator_id")),
            text(payload.get("version")) or "1",
            text(payload.get("status")) or "CANDIDATE",
            env,
            now,
            now,
        ),
    )
    return nid


def upsert_reasoning_seed(c, payload: Mapping[str, Any]) -> str:
    sid = text(payload.get("reasoning_seed_id"))
    if not sid:
        raise ValueError("reasoning_seed_id is required")
    seed_type = text(payload.get("seed_type")).upper() or "PRIMITIVE"
    weight = float(payload.get("independent_weight", 1.0) or 0)
    if seed_type == "PROVISIONAL_INTEGRATION":
        weight = 0.0
    env = _environment(text(payload.get("environment")) or ENV_LIVE)
    now = utcnow()
    c.execute(
        """INSERT INTO universal_reasoning_seeds(
          reasoning_seed_id,market_scope,programme,subject,chapter,unit,title,decisive_operation,seed_type,common_complexity,
          independent_weight,parent_seed_ids_json,source_id,version,status,environment,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(reasoning_seed_id) DO UPDATE SET market_scope=excluded.market_scope,programme=excluded.programme,
          subject=excluded.subject,chapter=excluded.chapter,unit=excluded.unit,title=excluded.title,
          decisive_operation=excluded.decisive_operation,seed_type=excluded.seed_type,common_complexity=excluded.common_complexity,
          independent_weight=excluded.independent_weight,parent_seed_ids_json=excluded.parent_seed_ids_json,
          source_id=excluded.source_id,version=excluded.version,status=excluded.status,environment=excluded.environment,updated_at=excluded.updated_at""",
        (
            sid,
            text(payload.get("market_scope")) or "UNIVERSAL",
            text(payload.get("programme")),
            text(payload.get("subject")),
            text(payload.get("chapter")),
            text(payload.get("unit")),
            text(payload.get("title")) or sid,
            text(payload.get("decisive_operation")) or sid,
            seed_type,
            text(payload.get("common_complexity")),
            weight,
            canonical_json(payload.get("parent_seed_ids") or []),
            text(payload.get("source_id")),
            text(payload.get("version")) or "1",
            text(payload.get("status")) or "CANDIDATE",
            env,
            now,
            now,
        ),
    )
    return sid


def upsert_claim_family_gate(c, payload: Mapping[str, Any]) -> str:
    gid = text(payload.get("gate_id"))
    fid = text(payload.get("claim_family_id"))
    nid = text(payload.get("knowledge_node_id"))
    if not gid or not fid or not nid:
        raise ValueError("gate_id, claim_family_id and knowledge_node_id are required")
    gate_type = text(payload.get("gate_type")).upper() or "REQUIRED_CORRECT"
    if gate_type not in GATE_TYPES:
        raise ValueError(f"Unsupported gate_type: {gate_type}")
    env = _environment(text(payload.get("environment")) or ENV_LIVE)
    c.execute(
        """INSERT INTO universal_claim_family_gates(
          gate_id,claim_family_id,knowledge_node_id,gate_type,trigger_json,closure_effect,required,version,status,environment,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(gate_id) DO UPDATE SET claim_family_id=excluded.claim_family_id,knowledge_node_id=excluded.knowledge_node_id,
          gate_type=excluded.gate_type,trigger_json=excluded.trigger_json,closure_effect=excluded.closure_effect,
          required=excluded.required,version=excluded.version,status=excluded.status,environment=excluded.environment""",
        (
            gid,
            fid,
            nid,
            gate_type,
            canonical_json(payload.get("trigger") or {}),
            text(payload.get("closure_effect")).upper() or "BLOCK",
            1 if truthy(payload.get("required", True)) else 0,
            text(payload.get("version")) or "1",
            text(payload.get("status")) or "ACTIVE",
            env,
            utcnow(),
        ),
    )
    return gid


def upsert_prerequisite_edge(c, payload: Mapping[str, Any]) -> str:
    eid = text(payload.get("prerequisite_edge_id"))
    if not eid:
        raise ValueError("prerequisite_edge_id is required")
    env = _environment(text(payload.get("environment")) or ENV_LIVE)
    c.execute(
        """INSERT INTO universal_prerequisite_edges(
          prerequisite_edge_id,from_entity_type,from_entity_id,to_entity_type,to_entity_id,edge_type,strength,
          source_id,source_locator_id,status,environment,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(prerequisite_edge_id) DO UPDATE SET from_entity_type=excluded.from_entity_type,
          from_entity_id=excluded.from_entity_id,to_entity_type=excluded.to_entity_type,to_entity_id=excluded.to_entity_id,
          edge_type=excluded.edge_type,strength=excluded.strength,source_id=excluded.source_id,
          source_locator_id=excluded.source_locator_id,status=excluded.status,environment=excluded.environment""",
        (
            eid,
            text(payload.get("from_entity_type")).upper(),
            text(payload.get("from_entity_id")),
            text(payload.get("to_entity_type")).upper(),
            text(payload.get("to_entity_id")),
            text(payload.get("edge_type")).upper() or "PREREQUISITE",
            text(payload.get("strength")).upper() or "MEDIUM",
            text(payload.get("source_id")),
            text(payload.get("source_locator_id")),
            text(payload.get("status")) or "CANDIDATE",
            env,
            utcnow(),
        ),
    )
    return eid


def upsert_question_architecture(c, payload: Mapping[str, Any]) -> str:
    qid = text(payload.get("architecture_question_id"))
    if not qid:
        raw = text(payload.get("external_question_id")) or text(payload.get("question_db_id"))
        if not raw:
            raise ValueError("architecture_question_id or question identity is required")
        qid = "UAQ-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    purpose = text(payload.get("purpose")).upper() or "SUBJECT_MASTERY"
    if purpose not in PURPOSES:
        raise ValueError(f"Unsupported question purpose: {purpose}")
    layer = text(payload.get("architecture_layer")).upper() or "L2_UNDERSTAND"
    if layer not in LAYERS:
        raise ValueError(f"Unsupported architecture layer: {layer}")
    context = text(payload.get("delivery_context")).upper() or "BLOCKED"
    if context not in DELIVERY_CONTEXTS:
        raise ValueError(f"Unsupported delivery context: {context}")
    dep = text(payload.get("dependency_type")).upper() or "DEPENDENT"
    weight = float(payload.get("independent_mastery_weight", 0) or 0)
    if purpose in {"RECOVERY"} or dep in {"VARIANT", "TRUE_VARIANT", "SCAFFOLD", "RECOVERY", "SHARED_STIMULUS_DEPENDENT", "DEPENDENT"}:
        weight = 0.0
    env = _environment(text(payload.get("environment")) or ENV_LIVE)
    now = utcnow()
    c.execute(
        """INSERT INTO universal_question_architecture(
          architecture_question_id,question_db_id,external_question_id,purpose,architecture_layer,pedagogical_type,
          authentic_exam_formats_json,independent_mastery_weight,parent_seed_id,dependency_type,transfer_level,
          surface_distance,delivery_context,confidence_required,evidence_validity,source_role,exam_mastery_eligible,
          environment,version,status,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(architecture_question_id) DO UPDATE SET question_db_id=excluded.question_db_id,
          external_question_id=excluded.external_question_id,purpose=excluded.purpose,architecture_layer=excluded.architecture_layer,
          pedagogical_type=excluded.pedagogical_type,authentic_exam_formats_json=excluded.authentic_exam_formats_json,
          independent_mastery_weight=excluded.independent_mastery_weight,parent_seed_id=excluded.parent_seed_id,
          dependency_type=excluded.dependency_type,transfer_level=excluded.transfer_level,surface_distance=excluded.surface_distance,
          delivery_context=excluded.delivery_context,confidence_required=excluded.confidence_required,evidence_validity=excluded.evidence_validity,
          source_role=excluded.source_role,exam_mastery_eligible=excluded.exam_mastery_eligible,environment=excluded.environment,
          version=excluded.version,status=excluded.status,updated_at=excluded.updated_at""",
        (
            qid,
            payload.get("question_db_id"),
            text(payload.get("external_question_id")),
            purpose,
            layer,
            text(payload.get("pedagogical_type")),
            canonical_json(payload.get("authentic_exam_formats") or []),
            weight,
            text(payload.get("parent_seed_id")),
            dep,
            text(payload.get("transfer_level")).upper() or "NEAR_COPY",
            float(payload.get("surface_distance", 0) or 0),
            context,
            1 if truthy(payload.get("confidence_required", False)) else 0,
            text(payload.get("evidence_validity")) or "VALID_IF_GOVERNED",
            text(payload.get("source_role")).upper() or "DIRECT",
            1 if truthy(payload.get("exam_mastery_eligible", True)) else 0,
            env,
            text(payload.get("version")) or "1",
            text(payload.get("status")) or "CANDIDATE",
            now,
            now,
        ),
    )
    # Optional mappings are written idempotently.
    for m in payload.get("node_mappings") or []:
        role = text(m.get("mapping_role")).upper() or "PRIMARY"
        c.execute(
            """INSERT INTO universal_question_node_map(architecture_question_id,knowledge_node_id,mapping_role,evidence_weight)
              VALUES(?,?,?,?) ON CONFLICT(architecture_question_id,knowledge_node_id) DO UPDATE SET
              mapping_role=excluded.mapping_role,evidence_weight=excluded.evidence_weight""",
            (qid, text(m.get("knowledge_node_id")), role, float(m.get("evidence_weight", 1) or 0)),
        )
    for m in payload.get("family_mappings") or []:
        role = text(m.get("mapping_role")).upper() or "PRIMARY"
        c.execute(
            """INSERT INTO universal_question_family_map(architecture_question_id,claim_family_id,mapping_role,evidence_weight)
              VALUES(?,?,?,?) ON CONFLICT(architecture_question_id,claim_family_id) DO UPDATE SET
              mapping_role=excluded.mapping_role,evidence_weight=excluded.evidence_weight""",
            (qid, text(m.get("claim_family_id")), role, float(m.get("evidence_weight", 1) or 0)),
        )
    for m in payload.get("seed_mappings") or []:
        role = text(m.get("mapping_role")).upper() or "PRIMARY"
        c.execute(
            """INSERT INTO universal_question_seed_map(architecture_question_id,reasoning_seed_id,mapping_role,evidence_weight)
              VALUES(?,?,?,?) ON CONFLICT(architecture_question_id,reasoning_seed_id) DO UPDATE SET
              mapping_role=excluded.mapping_role,evidence_weight=excluded.evidence_weight""",
            (qid, text(m.get("reasoning_seed_id")), role, float(m.get("evidence_weight", 1) or 0)),
        )
    return qid


def map_node_seed(c, knowledge_node_id: str, reasoning_seed_id: str, relation_type: str = "SUPPORTS", mapping_role: str = "SECONDARY", governance_status: str = "CANDIDATE") -> None:
    c.execute(
        """INSERT INTO universal_node_seed_map(knowledge_node_id,reasoning_seed_id,relation_type,mapping_role,governance_status)
          VALUES(?,?,?,?,?) ON CONFLICT(knowledge_node_id,reasoning_seed_id,relation_type) DO UPDATE SET
          mapping_role=excluded.mapping_role,governance_status=excluded.governance_status""",
        (knowledge_node_id, reasoning_seed_id, relation_type.upper(), mapping_role.upper(), governance_status),
    )


def upsert_exam_seed_profile(c, payload: Mapping[str, Any]) -> str:
    pid = text(payload.get("exam_seed_profile_id"))
    sid = text(payload.get("reasoning_seed_id"))
    rid = text(payload.get("exam_rule_set_id"))
    if not sid or not rid:
        raise ValueError("reasoning_seed_id and exam_rule_set_id are required")
    if not pid:
        pid = f"ESP:{sid}:{rid}:{text(payload.get('version')) or '1'}"
    c.execute(
        """INSERT INTO universal_exam_seed_profiles(
          exam_seed_profile_id,reasoning_seed_id,exam_rule_set_id,authentic_formats_json,difficulty_band,target_time_seconds,
          time_target_status,mastery_policy_json,version,status) VALUES(?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(exam_seed_profile_id) DO UPDATE SET authentic_formats_json=excluded.authentic_formats_json,
          difficulty_band=excluded.difficulty_band,target_time_seconds=excluded.target_time_seconds,time_target_status=excluded.time_target_status,
          mastery_policy_json=excluded.mastery_policy_json,version=excluded.version,status=excluded.status""",
        (
            pid,
            sid,
            rid,
            canonical_json(payload.get("authentic_formats") or []),
            text(payload.get("difficulty_band")),
            int(payload.get("target_time_seconds", 0) or 0),
            text(payload.get("time_target_status")).upper() or "INTERNAL",
            canonical_json(payload.get("mastery_policy") or {}),
            text(payload.get("version")) or "1",
            text(payload.get("status")) or "CANDIDATE",
        ),
    )
    return pid


def resolve_exam_rule_set(c, market: str, exam_code: str, exam_year: int, rule_version: str | None = None):
    params = [market.upper(), exam_code.upper(), int(exam_year)]
    sql = "SELECT * FROM universal_exam_rule_sets WHERE market=? AND exam_code=? AND exam_year=? AND status='ACTIVE'"
    if rule_version:
        sql += " AND rule_version=?"
        params.append(rule_version)
    sql += " ORDER BY CAST(rule_version AS INTEGER) DESC, exam_rule_set_id DESC LIMIT 1"
    return c.execute(sql, params).fetchone()


def score_exam_response(c, exam_rule_set_id: str, format_code: str, outcome: str, section_code: str = "") -> dict[str, Any]:
    outcome = text(outcome).upper()
    if outcome not in {"CORRECT", "WRONG", "BLANK"}:
        raise ValueError("outcome must be CORRECT, WRONG or BLANK")
    row = c.execute(
        """SELECT * FROM universal_exam_format_rules WHERE exam_rule_set_id=? AND format_code=?
          AND (?='' OR section_code=? OR section_code='') AND status='ACTIVE'
          ORDER BY CASE WHEN section_code=? THEN 0 ELSE 1 END LIMIT 1""",
        (exam_rule_set_id, format_code.upper(), section_code, section_code, section_code),
    ).fetchone()
    if not row:
        raise ValueError(f"No active scoring rule for {exam_rule_set_id}/{format_code}/{section_code}")
    marks = {"CORRECT": row["correct_marks"], "WRONG": row["wrong_marks"], "BLANK": row["blank_marks"]}[outcome]
    return {
        "exam_rule_set_id": exam_rule_set_id,
        "format_code": row["format_code"],
        "section_code": row["section_code"],
        "outcome": outcome,
        "marks": float(marks),
        "rule_id": row["exam_format_rule_id"],
        "answer_mode": row["answer_mode"],
    }


def _question_architecture(c, architecture_question_id: str = "", question_db_id: int | None = None):
    if architecture_question_id:
        return c.execute("SELECT * FROM universal_question_architecture WHERE architecture_question_id=?", (architecture_question_id,)).fetchone()
    if question_db_id is not None:
        return c.execute("SELECT * FROM universal_question_architecture WHERE question_db_id=?", (question_db_id,)).fetchone()
    return None


def _independence_key(qarch, seed_id: str = "") -> str:
    if seed_id:
        # Variants of a seed share one independence key so volume cannot inflate evidence.
        return f"SEED:{seed_id}"
    parent = text(qarch["parent_seed_id"] if qarch else "")
    if parent:
        return f"SEED:{parent}"
    if qarch:
        return f"QARCH:{qarch['architecture_question_id']}"
    return "UNMAPPED"


def _event_qualifying_weight(qarch, *, is_correct: bool, assistance_state: str, environment: str, transfer_level: str, evidence_role: str, mapping_weight: float = 1.0) -> tuple[float, bool]:
    if not is_correct:
        return 0.0, False
    if environment != ENV_LIVE and environment != ENV_QA:
        return 0.0, False
    if assistance_state != "UNASSISTED":
        return 0.0, False
    if evidence_role == "INCIDENTAL":
        return 0.0, False
    if not qarch:
        return 0.0, False
    if text(qarch["evidence_validity"]).upper() in {"INVALID", "NOT_VALID_FOR_MASTERY"}:
        return 0.0, False
    base = float(qarch["independent_mastery_weight"] or 0)
    # SOURCE_ONLY or explicitly exam-ineligible questions are learning/reference evidence,
    # never independent mastery closure evidence.
    if text(qarch["source_role"]).upper() == "SOURCE_ONLY" or not int(qarch["exam_mastery_eligible"] or 0):
        base = 0.0
    purpose = text(qarch["purpose"]).upper()
    dep = text(qarch["dependency_type"]).upper()
    if purpose == "RECOVERY" or dep in {"VARIANT", "TRUE_VARIANT", "SCAFFOLD", "RECOVERY", "SHARED_STIMULUS_DEPENDENT", "DEPENDENT"}:
        base = 0.0
    transfer_ok = text(transfer_level).upper() in {"UNSEEN_TRANSFER", "FAR_TRANSFER", "ALTERNATE_REPRESENTATION", "REVERSE_PROBLEM"}
    return max(0.0, base * max(0.0, float(mapping_weight))), transfer_ok


def record_response_event(
    c,
    *,
    learner_key: str,
    architecture_question_id: str = "",
    question_db_id: int | None = None,
    response_text: str = "",
    is_correct: bool,
    marks_awarded: float = 0.0,
    attempt_id: int | None = None,
    assessment_session_id: int | None = None,
    response_started_at: str = "",
    submitted_at: str | None = None,
    active_duration_seconds: int = 0,
    confidence_band: str = "",
    assistance_state: str = "UNASSISTED",
    attempt_state: str = "ATTEMPTED",
    delivery_context: str = "",
    exam_rule_set_id: str = "",
    exam_format_code: str = "",
    transfer_level: str = "",
    environment: str = ENV_LIVE,
    primary_error: str = "",
    secondary_error: str = "",
    diagnosis_confidence: str = "",
    misconception_id: str = "",
    ruleset_version: str = DEFAULT_RULESET_VERSION,
    response_event_id: str = "",
) -> dict[str, Any]:
    env = _environment(environment)
    learner = text(learner_key)
    if not learner:
        raise ValueError("learner_key is required")
    qarch = _question_architecture(c, architecture_question_id, question_db_id)
    if not qarch:
        raise ValueError("Question is not mapped to universal architecture")
    qid = qarch["architecture_question_id"]
    if text(qarch["environment"]) != env:
        raise ValueError("Question architecture environment does not match evidence environment")
    assistance = text(assistance_state).upper() or "UNASSISTED"
    if assistance not in ASSISTANCE_STATES:
        raise ValueError(f"Unsupported assistance state: {assistance}")
    confidence = text(confidence_band).upper().replace(" ", "_")
    aliases = {"FAIRLYSURE": "FAIRLY_SURE", "FAIRLY-SURE": "FAIRLY_SURE", "GUESSING": "GUESSED", "GUESS": "GUESSED"}
    confidence = aliases.get(confidence, confidence)
    if confidence not in CONFIDENCE_BANDS:
        raise ValueError(f"Unsupported confidence band: {confidence}")
    context = text(delivery_context).upper() or text(qarch["delivery_context"]).upper() or "BLOCKED"
    if context not in DELIVERY_CONTEXTS:
        raise ValueError(f"Unsupported delivery context: {context}")
    transfer = text(transfer_level).upper() or text(qarch["transfer_level"]).upper() or "NEAR_COPY"
    submitted = submitted_at or utcnow()
    payload = {
        "learner_key": learner,
        "architecture_question_id": qid,
        "question_db_id": question_db_id if question_db_id is not None else qarch["question_db_id"],
        "attempt_id": attempt_id,
        "assessment_session_id": assessment_session_id,
        "response_text": response_text,
        "is_correct": bool(is_correct),
        "marks_awarded": marks_awarded,
        "response_started_at": response_started_at,
        "submitted_at": submitted,
        "active_duration_seconds": max(0, int(active_duration_seconds or 0)),
        "confidence_band": confidence,
        "assistance_state": assistance,
        "attempt_state": text(attempt_state).upper() or "ATTEMPTED",
        "delivery_context": context,
        "exam_rule_set_id": exam_rule_set_id,
        "exam_format_code": text(exam_format_code).upper(),
        "transfer_level": transfer,
        "environment": env,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "ruleset_version": ruleset_version,
    }
    rid = response_event_id or "URE-" + hashlib.sha256((canonical_json(payload) + utcnow() + secrets.token_hex(8)).encode("utf-8")).hexdigest()[:24]
    c.execute(
        """INSERT INTO universal_response_events(
          response_event_id,learner_key,architecture_question_id,question_db_id,attempt_id,assessment_session_id,response_text,
          is_correct,marks_awarded,response_started_at,submitted_at,active_duration_seconds,confidence_band,assistance_state,
          attempt_state,delivery_context,exam_rule_set_id,exam_format_code,evidence_context,transfer_level,environment,evidence_validity,
          evidence_schema_version,ruleset_version,payload_checksum,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            rid,
            learner,
            qid,
            payload["question_db_id"],
            attempt_id,
            assessment_session_id,
            response_text,
            1 if is_correct else 0,
            float(marks_awarded or 0),
            response_started_at,
            submitted,
            payload["active_duration_seconds"],
            confidence,
            assistance,
            payload["attempt_state"],
            context,
            exam_rule_set_id,
            payload["exam_format_code"],
            context,
            transfer,
            env,
            "VALID" if env in VALID_ENVIRONMENTS else "INVALID",
            EVIDENCE_SCHEMA_VERSION,
            ruleset_version,
            checksum(payload),
            utcnow(),
        ),
    )
    if assistance != "UNASSISTED":
        aid = "UAE-" + hashlib.sha256(f"{rid}|{assistance}".encode()).hexdigest()[:24]
        c.execute(
            "INSERT OR IGNORE INTO universal_assistance_events(assistance_event_id,response_event_id,assistance_type,occurred_at) VALUES(?,?,?,?)",
            (aid, rid, assistance, submitted),
        )
    if not is_correct or primary_error:
        err = text(primary_error).upper() or ("OVERCONFIDENT_GUESS" if confidence == "CERTAIN" else "UNKNOWN")
        if err not in ERROR_CODES:
            err = "UNKNOWN"
        eid = "UER-" + hashlib.sha256(f"{rid}|{err}|{secondary_error}|{misconception_id}".encode()).hexdigest()[:24]
        c.execute(
            """INSERT OR IGNORE INTO universal_error_events(
              error_event_id,response_event_id,learner_key,primary_error,secondary_error,diagnostic_method,diagnosis_confidence,misconception_id,created_at)
              VALUES(?,?,?,?,?,'ITEM_SIGNAL',?,?,?)""",
            (eid, rid, learner, err, text(secondary_error).upper(), text(diagnosis_confidence).upper() or "LOW", text(misconception_id), utcnow()),
        )

    affected_nodes: set[str] = set()
    affected_families: set[str] = set()
    affected_seeds: set[str] = set()

    node_maps = c.execute("SELECT * FROM universal_question_node_map WHERE architecture_question_id=?", (qid,)).fetchall()
    family_maps = c.execute("SELECT * FROM universal_question_family_map WHERE architecture_question_id=?", (qid,)).fetchall()
    seed_maps = c.execute("SELECT * FROM universal_question_seed_map WHERE architecture_question_id=?", (qid,)).fetchall()

    # If family mappings were omitted, derive them from Knowledge Node -> Claim Family.
    if not family_maps and node_maps:
        # Collapse node-derived mappings by family. SOURCE_ONLY/ineligible nodes may diagnose
        # but cannot leak independent weight upward into a Claim Family.
        by_family: dict[str, dict[str, Any]] = {}
        for nm in node_maps:
            n = c.execute("SELECT claim_family_id,source_role,exam_mastery_eligible FROM universal_knowledge_nodes WHERE knowledge_node_id=?", (nm["knowledge_node_id"],)).fetchone()
            if not n:
                continue
            eligible = text(n["source_role"]).upper() != "SOURCE_ONLY" and int(n["exam_mastery_eligible"] or 0) == 1
            candidate = {
                "claim_family_id": n["claim_family_id"],
                "mapping_role": text(nm["mapping_role"]).upper() if eligible else "INCIDENTAL",
                "evidence_weight": float(nm["evidence_weight"] or 0) if eligible else 0.0,
            }
            existing = by_family.get(n["claim_family_id"])
            if existing is None or float(candidate["evidence_weight"]) > float(existing["evidence_weight"]):
                by_family[n["claim_family_id"]] = candidate
        family_maps = list(by_family.values())

    for nm in node_maps:
        role = text(nm["mapping_role"]).upper()
        w, transfer_ok = _event_qualifying_weight(
            qarch,
            is_correct=bool(is_correct),
            assistance_state=assistance,
            environment=env,
            transfer_level=transfer,
            evidence_role=role,
            mapping_weight=float(nm["evidence_weight"] or 0),
        )
        node = c.execute("SELECT * FROM universal_knowledge_nodes WHERE knowledge_node_id=?", (nm["knowledge_node_id"],)).fetchone()
        if node and (text(node["source_role"]).upper() == "SOURCE_ONLY" or not int(node["exam_mastery_eligible"] or 0)):
            w = 0.0
        seed_hint = text(qarch["parent_seed_id"])
        ikey = _independence_key(qarch, seed_hint)
        c.execute(
            """INSERT OR IGNORE INTO universal_node_evidence(
              learner_key,knowledge_node_id,response_event_id,independence_key,is_correct,qualifying_weight,transfer_qualifies,evidence_role,environment,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (learner, nm["knowledge_node_id"], rid, ikey, 1 if is_correct else 0, w, 1 if transfer_ok else 0, role, env, utcnow()),
        )
        affected_nodes.add(nm["knowledge_node_id"])

    for fm in family_maps:
        role = text(fm["mapping_role"]).upper()
        w, transfer_ok = _event_qualifying_weight(
            qarch,
            is_correct=bool(is_correct),
            assistance_state=assistance,
            environment=env,
            transfer_level=transfer,
            evidence_role=role,
            mapping_weight=float(fm["evidence_weight"] or 0),
        )
        family = c.execute("SELECT independent_weight FROM universal_claim_families WHERE claim_family_id=?", (fm["claim_family_id"],)).fetchone()
        if family:
            w = min(w, float(family["independent_weight"] or 0))
        ikey = _independence_key(qarch, text(qarch["parent_seed_id"]))
        c.execute(
            """INSERT OR IGNORE INTO universal_family_evidence(
              learner_key,claim_family_id,response_event_id,independence_key,is_correct,qualifying_weight,transfer_qualifies,evidence_role,environment,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (learner, fm["claim_family_id"], rid, ikey, 1 if is_correct else 0, w, 1 if transfer_ok else 0, role, env, utcnow()),
        )
        affected_families.add(fm["claim_family_id"])

    for sm in seed_maps:
        role = text(sm["mapping_role"]).upper()
        w, transfer_ok = _event_qualifying_weight(
            qarch,
            is_correct=bool(is_correct),
            assistance_state=assistance,
            environment=env,
            transfer_level=transfer,
            evidence_role=role,
            mapping_weight=float(sm["evidence_weight"] or 0),
        )
        seed = c.execute("SELECT independent_weight FROM universal_reasoning_seeds WHERE reasoning_seed_id=?", (sm["reasoning_seed_id"],)).fetchone()
        if seed:
            w = min(w, float(seed["independent_weight"] or 0))
        ikey = _independence_key(qarch, sm["reasoning_seed_id"])
        c.execute(
            """INSERT OR IGNORE INTO universal_seed_evidence(
              learner_key,reasoning_seed_id,response_event_id,independence_key,is_correct,qualifying_weight,transfer_qualifies,evidence_role,environment,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (learner, sm["reasoning_seed_id"], rid, ikey, 1 if is_correct else 0, w, 1 if transfer_ok else 0, role, env, utcnow()),
        )
        affected_seeds.add(sm["reasoning_seed_id"])

    node_states = [recalculate_entity_state(c, learner, "NODE", x, env, rid, ruleset_version) for x in sorted(affected_nodes)]
    family_states = [recalculate_entity_state(c, learner, "FAMILY", x, env, rid, ruleset_version) for x in sorted(affected_families)]
    seed_states = [recalculate_entity_state(c, learner, "SEED", x, env, rid, ruleset_version) for x in sorted(affected_seeds)]

    exam_states = []
    if exam_rule_set_id:
        for sid in sorted(affected_seeds):
            exam_states.append(recalculate_exam_seed_state(c, learner, sid, exam_rule_set_id, env, ruleset_version))

    return {
        "response_event_id": rid,
        "nodes": node_states,
        "families": family_states,
        "seeds": seed_states,
        "exam_seed_states": exam_states,
        "environment": env,
    }


def _evidence_table(entity_type: str) -> tuple[str, str, str]:
    et = entity_type.upper()
    if et == "NODE":
        return "universal_node_evidence", "knowledge_node_id", "universal_learner_node_state"
    if et == "FAMILY":
        return "universal_family_evidence", "claim_family_id", "universal_learner_family_state"
    if et == "SEED":
        return "universal_seed_evidence", "reasoning_seed_id", "universal_learner_seed_state"
    raise ValueError(f"Unsupported entity type: {entity_type}")


def _entity_policy(c, entity_type: str, entity_id: str) -> dict[str, Any]:
    et = entity_type.upper()
    if et == "FAMILY":
        row = c.execute("SELECT closure_policy_json FROM universal_claim_families WHERE claim_family_id=?", (entity_id,)).fetchone()
        policy = dict(DEFAULT_FAMILY_POLICY)
        if row:
            policy.update(safe_json(row["closure_policy_json"], {}) or {})
        return policy
    if et == "SEED":
        return dict(DEFAULT_SEED_POLICY)
    return dict(DEFAULT_NODE_POLICY)


def _gate_evaluation(c, learner_key: str, claim_family_id: str, environment: str) -> dict[str, Any]:
    gates = c.execute(
        "SELECT * FROM universal_claim_family_gates WHERE claim_family_id=? AND environment=? AND status='ACTIVE' ORDER BY gate_id",
        (claim_family_id, environment),
    ).fetchall()
    result = {"blocked": False, "failed": [], "untested_required": [], "passed": []}
    for gate in gates:
        rows = c.execute(
            """SELECT ne.*,re.confidence_band,re.assistance_state,re.delivery_context FROM universal_node_evidence ne
              JOIN universal_response_events re ON re.response_event_id=ne.response_event_id
              WHERE ne.learner_key=? AND ne.knowledge_node_id=? AND ne.environment=? ORDER BY ne.id DESC LIMIT 20""",
            (learner_key, gate["knowledge_node_id"], environment),
        ).fetchall()
        gate_type = text(gate["gate_type"]).upper()
        status = "UNTESTED"
        if rows:
            # Evaluate the most recent decisive gate evidence so a later governed, unassisted
            # correction can repair a previously failed misconception gate.
            correct_qual = lambda r: bool(int(r["is_correct"] or 0) and float(r["qualifying_weight"] or 0) > 0)
            high_conf_wrong = lambda r: bool((not int(r["is_correct"] or 0)) and text(r["confidence_band"]).upper() == "CERTAIN")
            if gate_type in {"MISCONCEPTION_GUARD", "HIGH_CONFIDENCE_WRONG"}:
                decisive = next((r for r in rows if high_conf_wrong(r) or correct_qual(r)), None)
                if decisive is not None:
                    status = "FAILED" if high_conf_wrong(decisive) else "PASSED"
            elif gate_type == "REPEATED_WRONG":
                streak = 0
                for r in rows:
                    if correct_qual(r):
                        break
                    if not int(r["is_correct"] or 0):
                        streak += 1
                if streak >= 2:
                    status = "FAILED"
                elif any(correct_qual(r) for r in rows):
                    status = "PASSED"
            elif gate_type == "REQUIRED_CORRECT":
                decisive = next((r for r in rows if correct_qual(r) or not int(r["is_correct"] or 0)), None)
                if decisive is not None:
                    status = "PASSED" if correct_qual(decisive) else "FAILED"
            else:
                decisive = next((r for r in rows if high_conf_wrong(r) or correct_qual(r)), None)
                if decisive is not None:
                    status = "FAILED" if high_conf_wrong(decisive) else "PASSED"
        if status == "FAILED":
            result["failed"].append(gate["gate_id"])
            if text(gate["closure_effect"]).upper() in {"BLOCK", "REOPEN"}:
                result["blocked"] = True
        elif status == "UNTESTED" and int(gate["required"] or 0):
            result["untested_required"].append(gate["gate_id"])
            result["blocked"] = True
        elif status == "PASSED":
            result["passed"].append(gate["gate_id"])
    return result


def _active_reverification_boundary(c, learner_key: str, entity_type: str, entity_id: str, environment: str):
    """Return the latest still-active reopen/at-risk/maintenance transition.

    Historical positives earned before that boundary may remain useful history, but they
    cannot re-close the entity. The learner must rebuild the closure requirements with
    fresh qualifying evidence after the boundary. Two indexed point-lookups avoid turning
    large simulation/replay runs into an O(history-size) scan on every response.
    """
    args=(learner_key,entity_type.upper(),entity_id,environment)
    boundary=c.execute(
        """SELECT rowid AS _rid,* FROM universal_mastery_state_history
           WHERE learner_key=? AND entity_type=? AND entity_id=? AND environment=?
             AND new_state IN ('REOPENED','AT_RISK','MAINTENANCE_DUE')
           ORDER BY rowid DESC LIMIT 1""", args).fetchone()
    if boundary is None:
        return None
    verified=c.execute(
        """SELECT rowid AS _rid FROM universal_mastery_state_history
           WHERE learner_key=? AND entity_type=? AND entity_id=? AND environment=?
             AND new_state='VERIFIED_MASTERED'
           ORDER BY rowid DESC LIMIT 1""", args).fetchone()
    if verified is not None and int(verified["_rid"])>int(boundary["_rid"]):
        return None
    return boundary


def _rows_after_reverification_boundary(rows: Sequence[Mapping[str, Any]], boundary) -> list[Mapping[str, Any]]:
    if not boundary:
        return list(rows)
    event_id=text(boundary["response_event_id"])
    if event_id:
        boundary_ids=[int(r["id"]) for r in rows if text(r["response_event_id"])==event_id]
        if boundary_ids:
            cutoff=max(boundary_ids)
            return [r for r in rows if int(r["id"])>cutoff]
    cutoff=text(boundary["created_at"])
    return [r for r in rows if text(r["created_at"])>cutoff]


def _route_capped_weight(rows: Sequence[Mapping[str, Any]]) -> tuple[float, int, bool, int, int]:
    route_weight: dict[str, float] = {}
    transfer_ok = False
    total_correct = 0
    total_wrong = 0
    for r in rows:
        if int(r["is_correct"] or 0):
            total_correct += 1
            if int(r["transfer_qualifies"] or 0):
                transfer_ok = True
            key = text(r["independence_key"]) or f"ROW:{r['id']}"
            route_weight[key] = max(route_weight.get(key, 0.0), float(r["qualifying_weight"] or 0))
        else:
            total_wrong += 1
    return sum(route_weight.values()), sum(1 for v in route_weight.values() if v > 0), transfer_ok, total_correct, total_wrong


def recalculate_entity_state(c, learner_key: str, entity_type: str, entity_id: str, environment: str = ENV_LIVE, response_event_id: str = "", ruleset_version: str = DEFAULT_RULESET_VERSION) -> dict[str, Any]:
    env = _environment(environment)
    table, id_col, state_table = _evidence_table(entity_type)
    rows = c.execute(
        f"SELECT * FROM {table} WHERE learner_key=? AND {id_col}=? AND environment=? ORDER BY id",
        (learner_key, entity_id, env),
    ).fetchall()
    policy = _entity_policy(c, entity_type, entity_id)
    current = c.execute(
        f"SELECT * FROM {state_table} WHERE learner_key=? AND {id_col}=? AND environment=?",
        (learner_key, entity_id, env),
    ).fetchone()
    old_state = current["state"] if current else "UNSEEN"
    # Once an entity has been reopened / placed at risk / marked maintenance-due,
    # closure is prospective. Pre-boundary positives cannot be recycled to re-verify it.
    reverification_boundary=_active_reverification_boundary(c,learner_key,entity_type,entity_id,env)
    closure_rows=_rows_after_reverification_boundary(rows,reverification_boundary)
    weight, routes, transfer_ok, correct_count, wrong_count = _route_capped_weight(closure_rows)
    latest_event = None
    if rows:
        latest_event = c.execute("SELECT * FROM universal_response_events WHERE response_event_id=?", (rows[-1]["response_event_id"],)).fetchone()
    gate = {"blocked": False, "failed": [], "untested_required": [], "passed": []}
    if entity_type.upper() == "FAMILY":
        gate = _gate_evaluation(c, learner_key, entity_id, env)

    if not rows:
        new_state = "UNSEEN"
    elif correct_count == 0:
        new_state = "LEARNING"
    else:
        min_routes = int(policy.get("min_distinct_routes", 1) or 1)
        min_weight = float(policy.get("min_qualifying_weight", 1.0) or 0)
        require_transfer = bool(policy.get("require_unseen_transfer", False))
        base_ready = weight >= min_weight and routes >= min_routes
        transfer_ready = transfer_ok or not require_transfer
        if base_ready and transfer_ready and not gate["blocked"]:
            new_state = "VERIFIED_MASTERED"
        elif weight > 0:
            new_state = "PROVISIONALLY_MASTERED"
        else:
            new_state = "LEARNING"

    # Contradictory evidence is evaluated even when old positive evidence still satisfies
    # aggregate thresholds. Otherwise verified mastery could become mathematically immortal.
    # Interleaved/authentic-exam failures remain protected unless a mandatory hard gate fails.
    if current and old_state in {"REOPENED", "AT_RISK"} and rows:
        latest_row = rows[-1]
        latest_wrong_now = not int(latest_row["is_correct"] or 0)
        if latest_wrong_now:
            threshold = max(1, int(policy.get("reopen_wrong_threshold", 2) or 2))
            recent = rows[-threshold:]
            qualifying_wrong = sum(1 for r in recent if not int(r["is_correct"] or 0))
            new_state = "REOPENED" if old_state == "REOPENED" or qualifying_wrong >= threshold else "AT_RISK"
        elif float(latest_row["qualifying_weight"] or 0) <= 0:
            # Assisted/dependent/invalid recovery activity cannot silently re-close an
            # already reopened or at-risk entity.
            new_state = old_state

    if current and old_state in {"VERIFIED_MASTERED", "MAINTENANCE_DUE"}:
        latest_context = text(latest_event["delivery_context"]).upper() if latest_event else ""
        latest_wrong = bool(latest_event and not int(latest_event["is_correct"] or 0))
        high_conf_wrong = bool(latest_wrong and text(latest_event["confidence_band"]).upper() == "CERTAIN")
        if entity_type.upper() == "FAMILY" and gate["failed"]:
            new_state = "REOPENED"
        elif latest_wrong:
            if high_conf_wrong and entity_type.upper() == "FAMILY":
                new_state = "AT_RISK"
            elif latest_context in {"INTERLEAVED", "AUTHENTIC_EXAM"}:
                new_state = old_state
            else:
                threshold = max(1, int(policy.get("reopen_wrong_threshold", 2) or 2))
                recent = rows[-threshold:]
                qualifying_wrong = sum(1 for r in recent if not int(r["is_correct"] or 0))
                new_state = "REOPENED" if qualifying_wrong >= threshold else old_state
        elif new_state not in {"VERIFIED_MASTERED", "MAINTENANCE_DUE"}:
            # A ruleset/policy change alone does not silently erase historical verified
            # mastery in the pilot; stronger rules apply prospectively through new evidence.
            new_state = old_state

    last_verified_at = current["last_verified_at"] if current else ""
    due_at = current["maintenance_due_at"] if current else ""
    if new_state == "VERIFIED_MASTERED" and old_state != "VERIFIED_MASTERED":
        last_verified_at = utcnow()
        due_at = (_today() + timedelta(days=int(policy.get("verification_days", 90) or 90))).isoformat()
    elif new_state == "VERIFIED_MASTERED" and not due_at:
        due_at = (_today() + timedelta(days=int(policy.get("verification_days", 90) or 90))).isoformat()

    confidence = "HIGH" if routes >= max(2, int(policy.get("min_distinct_routes", 1) or 1)) and weight >= float(policy.get("min_qualifying_weight", 1.0) or 0) else ("MEDIUM" if weight > 0 else "LOW")
    reopen_reason = ""
    if new_state == "REOPENED":
        reopen_reason = "MANDATORY_GATE_FAILED" if gate["failed"] else "VALIDATED_CONTRADICTORY_EVIDENCE"
    elif new_state == "AT_RISK":
        reopen_reason = "HIGH_CONFIDENCE_WRONG"

    columns = {
        "NODE": "knowledge_node_id",
        "FAMILY": "claim_family_id",
        "SEED": "reasoning_seed_id",
    }
    idname = columns[entity_type.upper()]
    fields = "learner_key," + idname + ",environment,state,evidence_confidence,last_evidence_at,last_verified_at,maintenance_due_at,reopen_reason,retention_risk,ruleset_version,updated_at"
    placeholders = ",".join("?" for _ in range(12))
    vals = [learner_key, entity_id, env, new_state, confidence, utcnow() if rows else "", last_verified_at, due_at, reopen_reason, "LOW", ruleset_version, utcnow()]
    if entity_type.upper() == "FAMILY":
        fields = "learner_key,claim_family_id,environment,state,evidence_confidence,last_evidence_at,last_verified_at,maintenance_due_at,reopen_reason,gate_status_json,retention_risk,ruleset_version,updated_at"
        placeholders = ",".join("?" for _ in range(13))
        vals = [learner_key, entity_id, env, new_state, confidence, utcnow() if rows else "", last_verified_at, due_at, reopen_reason, canonical_json(gate), "LOW", ruleset_version, utcnow()]
        update = "state=excluded.state,evidence_confidence=excluded.evidence_confidence,last_evidence_at=excluded.last_evidence_at,last_verified_at=excluded.last_verified_at,maintenance_due_at=excluded.maintenance_due_at,reopen_reason=excluded.reopen_reason,gate_status_json=excluded.gate_status_json,retention_risk=excluded.retention_risk,ruleset_version=excluded.ruleset_version,updated_at=excluded.updated_at"
    else:
        update = "state=excluded.state,evidence_confidence=excluded.evidence_confidence,last_evidence_at=excluded.last_evidence_at,last_verified_at=excluded.last_verified_at,maintenance_due_at=excluded.maintenance_due_at,reopen_reason=excluded.reopen_reason,retention_risk=excluded.retention_risk,ruleset_version=excluded.ruleset_version,updated_at=excluded.updated_at"
    c.execute(
        f"INSERT INTO {state_table}({fields}) VALUES({placeholders}) ON CONFLICT(learner_key,{idname},environment) DO UPDATE SET {update}",
        vals,
    )

    if new_state != old_state:
        _record_state_transition(c, learner_key, entity_type.upper(), entity_id, env, old_state, new_state, reopen_reason or "EVIDENCE_RECALCULATION", response_event_id, ruleset_version)
    _log_decision(
        c,
        learner_key=learner_key,
        decision_type="MASTERY_STATE",
        entity_type=entity_type.upper(),
        entity_id=entity_id,
        environment=env,
        inputs={
            "weight": weight,
            "distinct_routes": routes,
            "transfer_ok": transfer_ok,
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "gate": gate,
            "policy": policy,
            "old_state": old_state,
            "reverification_boundary": dict(reverification_boundary) if reverification_boundary else None,
            "closure_evidence_count": len(closure_rows),
        },
        output={"state": new_state, "evidence_confidence": confidence, "maintenance_due_at": due_at},
        ruleset_version=ruleset_version,
    )

    if new_state in {"REOPENED", "AT_RISK"}:
        _open_recovery(c, learner_key, entity_type.upper(), entity_id, reopen_reason or "MASTERY_AT_RISK", env, priority=1 if gate["failed"] else 2)
    elif new_state == "VERIFIED_MASTERED":
        _close_recovery(c, learner_key, entity_type.upper(), entity_id, env)
        _schedule_maintenance(c, learner_key, entity_type.upper(), entity_id, due_at, env)

    return {
        "entity_type": entity_type.upper(),
        "entity_id": entity_id,
        "state": new_state,
        "old_state": old_state,
        "qualifying_weight": round(weight, 4),
        "distinct_routes": routes,
        "transfer_ok": transfer_ok,
        "gate": gate,
        "environment": env,
    }


def _record_state_transition(c, learner_key: str, entity_type: str, entity_id: str, environment: str, old_state: str, new_state: str, reason_code: str, response_event_id: str, ruleset_version: str) -> None:
    hid = "UMH-" + hashlib.sha256(f"{learner_key}|{entity_type}|{entity_id}|{old_state}|{new_state}|{response_event_id}|{utcnow()}|{secrets.token_hex(8)}".encode()).hexdigest()[:24]
    c.execute(
        """INSERT INTO universal_mastery_state_history(
          history_id,learner_key,entity_type,entity_id,environment,old_state,new_state,reason_code,response_event_id,
          evidence_refs_json,ruleset_version,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (hid, learner_key, entity_type, entity_id, environment, old_state, new_state, reason_code, response_event_id, canonical_json([response_event_id] if response_event_id else []), ruleset_version, utcnow()),
    )


def _log_decision(c, *, learner_key: str = "", decision_type: str, entity_type: str = "", entity_id: str = "", environment: str = ENV_LIVE, inputs: Mapping[str, Any], output: Mapping[str, Any], ruleset_version: str = DEFAULT_RULESET_VERSION) -> str:
    payload = canonical_json(inputs)
    did = "UMD-" + hashlib.sha256(f"{learner_key}|{decision_type}|{entity_type}|{entity_id}|{payload}|{canonical_json(output)}|{utcnow()}|{secrets.token_hex(8)}".encode()).hexdigest()[:24]
    c.execute(
        """INSERT INTO universal_decision_log(
          decision_id,learner_key,decision_type,entity_type,entity_id,environment,input_json,input_checksum,output_json,
          ruleset_version,architecture_version,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (did, learner_key, decision_type, entity_type, entity_id, environment, payload, checksum(inputs), canonical_json(output), ruleset_version, ARCHITECTURE_VERSION, utcnow()),
    )
    return did


def replay_entity_state(c, learner_key: str, entity_type: str, entity_id: str, environment: str = ENV_LIVE, ruleset_version: str = DEFAULT_RULESET_VERSION) -> dict[str, Any]:
    """Deterministically recompute the decision and return the latest decision checksum/output.

    The event sequence is immutable; replay uses the same ruleset and partition. The result must
    match repeated replays unless the ruleset version changes.
    """
    result = recalculate_entity_state(c, learner_key, entity_type, entity_id, environment, "", ruleset_version)
    row = c.execute(
        """SELECT * FROM universal_decision_log WHERE learner_key=? AND decision_type='MASTERY_STATE'
          AND entity_type=? AND entity_id=? AND environment=? AND ruleset_version=? ORDER BY rowid DESC LIMIT 1""",
        (learner_key, entity_type.upper(), entity_id, environment, ruleset_version),
    ).fetchone()
    return {"result": result, "input_checksum": row["input_checksum"] if row else "", "output": safe_json(row["output_json"], {}) if row else {}}


def _open_recovery(c, learner_key: str, entity_type: str, entity_id: str, cause_code: str, environment: str, priority: int = 2, cause_detail: str = "") -> str:
    existing = c.execute(
        """SELECT recovery_id FROM universal_recovery_queue WHERE learner_key=? AND entity_type=? AND entity_id=?
          AND status='OPEN' AND environment=? ORDER BY priority LIMIT 1""",
        (learner_key, entity_type, entity_id, environment),
    ).fetchone()
    if existing:
        c.execute(
            "UPDATE universal_recovery_queue SET priority=MIN(priority,?),cause_code=?,cause_detail=?,updated_at=? WHERE recovery_id=?",
            (priority, cause_code, cause_detail, utcnow(), existing["recovery_id"]),
        )
        return existing["recovery_id"]
    rid = "URQ-" + hashlib.sha256(f"{learner_key}|{entity_type}|{entity_id}|{cause_code}|{environment}|{utcnow()}".encode()).hexdigest()[:24]
    c.execute(
        """INSERT INTO universal_recovery_queue(
          recovery_id,learner_key,entity_type,entity_id,cause_code,cause_detail,priority,required_evidence,status,due_at,environment,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,'UNASSISTED_TRANSFER','OPEN',?,?,?,?)""",
        (rid, learner_key, entity_type, entity_id, cause_code, cause_detail, priority, (_today() + timedelta(days=1)).isoformat(), environment, utcnow(), utcnow()),
    )
    return rid


def _close_recovery(c, learner_key: str, entity_type: str, entity_id: str, environment: str) -> None:
    c.execute(
        "UPDATE universal_recovery_queue SET status='CLOSED',updated_at=? WHERE learner_key=? AND entity_type=? AND entity_id=? AND environment=? AND status='OPEN'",
        (utcnow(), learner_key, entity_type, entity_id, environment),
    )


def _schedule_maintenance(c, learner_key: str, entity_type: str, entity_id: str, due_at: str, environment: str) -> None:
    if not due_at:
        return
    existing = c.execute(
        """SELECT maintenance_id FROM universal_maintenance_queue WHERE learner_key=? AND entity_type=? AND entity_id=?
          AND status='OPEN' AND environment=?""",
        (learner_key, entity_type, entity_id, environment),
    ).fetchone()
    if existing:
        c.execute("UPDATE universal_maintenance_queue SET due_at=? WHERE maintenance_id=?", (due_at, existing["maintenance_id"]))
        return
    mid = "UMQ-" + hashlib.sha256(f"{learner_key}|{entity_type}|{entity_id}|{due_at}|{environment}".encode()).hexdigest()[:24]
    c.execute(
        """INSERT INTO universal_maintenance_queue(
          maintenance_id,learner_key,entity_type,entity_id,due_at,retention_risk,reason,status,environment,created_at)
          VALUES(?,?,?,?,?,'LOW','EVIDENCE_FRESHNESS','OPEN',?,?)""",
        (mid, learner_key, entity_type, entity_id, due_at, environment, utcnow()),
    )


def apply_maintenance_due(c, *, as_of: date | datetime | str | None = None, environment: str = ENV_LIVE, learner_key: str = "") -> int:
    env = _environment(environment)
    today = _today(as_of).isoformat()
    count = 0
    for table, idcol, etype in [
        ("universal_learner_node_state", "knowledge_node_id", "NODE"),
        ("universal_learner_family_state", "claim_family_id", "FAMILY"),
        ("universal_learner_seed_state", "reasoning_seed_id", "SEED"),
    ]:
        params: list[Any] = [env, today]
        learner_clause = ""
        if learner_key:
            learner_clause = " AND learner_key=?"
            params.append(learner_key)
        rows = c.execute(
            f"SELECT * FROM {table} WHERE environment=? AND state='VERIFIED_MASTERED' AND maintenance_due_at<>'' AND date(maintenance_due_at)<=date(?) {learner_clause}",
            params,
        ).fetchall()
        for row in rows:
            c.execute(
                f"UPDATE {table} SET state='MAINTENANCE_DUE',retention_risk='MEDIUM',updated_at=? WHERE learner_key=? AND {idcol}=? AND environment=?",
                (utcnow(), row["learner_key"], row[idcol], env),
            )
            # Pin the maintenance boundary to the last evidence event. Timestamp-only
            # boundaries can be ambiguous because event/state timestamps are second-granular.
            evidence_table,evidence_idcol,_=_evidence_table(etype)
            last_evidence=c.execute(
                f"SELECT response_event_id FROM {evidence_table} WHERE learner_key=? AND {evidence_idcol}=? AND environment=? ORDER BY id DESC LIMIT 1",
                (row["learner_key"],row[idcol],env),
            ).fetchone()
            boundary_event=last_evidence["response_event_id"] if last_evidence else ""
            _record_state_transition(c, row["learner_key"], etype, row[idcol], env, "VERIFIED_MASTERED", "MAINTENANCE_DUE", "EVIDENCE_FRESHNESS_DUE", boundary_event, row["ruleset_version"])
            _schedule_maintenance(c, row["learner_key"], etype, row[idcol], row["maintenance_due_at"], env)
            count += 1
    return count


def prerequisite_candidates(c, entity_type: str, entity_id: str, environment: str = ENV_LIVE) -> list[dict[str, Any]]:
    rows = c.execute(
        """SELECT * FROM universal_prerequisite_edges WHERE to_entity_type=? AND to_entity_id=? AND environment=? AND status IN ('ACTIVE','CANDIDATE')
          ORDER BY CASE strength WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END, prerequisite_edge_id""",
        (entity_type.upper(), entity_id, environment),
    ).fetchall()
    return [dict(r) for r in rows]


def diagnose_prerequisite(c, *, learner_key: str, target_entity_type: str, target_entity_id: str, prerequisite_edge_id: str, result: str, diagnosis_confidence: str = "MEDIUM", response_event_id: str = "", environment: str = ENV_LIVE) -> str:
    edge = c.execute("SELECT * FROM universal_prerequisite_edges WHERE prerequisite_edge_id=?", (prerequisite_edge_id,)).fetchone()
    if not edge:
        raise ValueError("Unknown prerequisite edge")
    did = "UPD-" + hashlib.sha256(f"{learner_key}|{target_entity_type}|{target_entity_id}|{prerequisite_edge_id}|{result}|{utcnow()}".encode()).hexdigest()[:24]
    c.execute(
        """INSERT INTO universal_prerequisite_diagnostics(
          diagnostic_id,learner_key,target_entity_type,target_entity_id,prerequisite_edge_id,result,diagnosis_confidence,response_event_id,environment,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (did, learner_key, target_entity_type.upper(), target_entity_id, prerequisite_edge_id, result.upper(), diagnosis_confidence.upper(), response_event_id, environment, utcnow()),
    )
    if result.upper() == "PREREQUISITE_GAP_CONFIRMED":
        _open_recovery(c, learner_key, edge["from_entity_type"], edge["from_entity_id"], "PREREQUISITE_GAP", environment, priority=1, cause_detail=f"Before {target_entity_id}")
    return did


def recalculate_exam_seed_state(c, learner_key: str, reasoning_seed_id: str, exam_rule_set_id: str, environment: str = ENV_LIVE, ruleset_version: str = DEFAULT_RULESET_VERSION) -> dict[str, Any]:
    profile = c.execute(
        "SELECT * FROM universal_exam_seed_profiles WHERE reasoning_seed_id=? AND exam_rule_set_id=? AND status IN ('ACTIVE','CANDIDATE') ORDER BY version DESC LIMIT 1",
        (reasoning_seed_id, exam_rule_set_id),
    ).fetchone()
    if not profile:
        return {"reasoning_seed_id": reasoning_seed_id, "exam_rule_set_id": exam_rule_set_id, "state": "UNSEEN", "reason": "NO_PROFILE"}
    rows = c.execute(
        """SELECT se.*,re.active_duration_seconds,re.delivery_context,re.exam_format_code,re.is_correct,re.assistance_state
          FROM universal_seed_evidence se JOIN universal_response_events re ON re.response_event_id=se.response_event_id
          WHERE se.learner_key=? AND se.reasoning_seed_id=? AND se.environment=? AND re.exam_rule_set_id=?
          ORDER BY se.id""",
        (learner_key, reasoning_seed_id, environment, exam_rule_set_id),
    ).fetchall()
    authentic_formats = {text(x).upper() for x in safe_json(profile["authentic_formats_json"], [])}
    authentic = [r for r in rows if text(r["exam_format_code"]).upper() in authentic_formats and text(r["delivery_context"]).upper() == "AUTHENTIC_EXAM"]
    correct = [r for r in authentic if int(r["is_correct"] or 0) and text(r["assistance_state"]).upper() == "UNASSISTED"]
    target = int(profile["target_time_seconds"] or 0)
    fluent = [r for r in correct if not target or int(r["active_duration_seconds"] or 0) <= target]
    if not authentic:
        state = "UNSEEN"
        score = None
        fluency = "UNASSESSED"
    else:
        score = round(100.0 * len(correct) / len(authentic), 1)
        fluency = "READY" if correct and len(fluent) == len(correct) else ("DEVELOPING" if correct else "NOT_READY")
        policy = safe_json(profile["mastery_policy_json"], {}) or {}
        min_events = int(policy.get("min_authentic_events", 2) or 2)
        min_accuracy = float(policy.get("min_accuracy", 70) or 70)
        require_fluency = bool(policy.get("require_fluency", True))
        if len(authentic) >= min_events and score >= min_accuracy and (not require_fluency or fluency == "READY"):
            state = "VERIFIED_MASTERED"
        elif correct:
            state = "PROVISIONALLY_MASTERED"
        else:
            state = "LEARNING"
    c.execute(
        """INSERT INTO universal_learner_exam_seed_state(
          learner_key,reasoning_seed_id,exam_rule_set_id,environment,state,readiness_score,fluency_state,evidence_count,last_verified_at,ruleset_version,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(learner_key,reasoning_seed_id,exam_rule_set_id,environment) DO UPDATE SET
          state=excluded.state,readiness_score=excluded.readiness_score,fluency_state=excluded.fluency_state,evidence_count=excluded.evidence_count,
          last_verified_at=excluded.last_verified_at,ruleset_version=excluded.ruleset_version,updated_at=excluded.updated_at""",
        (learner_key, reasoning_seed_id, exam_rule_set_id, environment, state, score, fluency, len(authentic), utcnow() if state == "VERIFIED_MASTERED" else "", ruleset_version, utcnow()),
    )
    _log_decision(
        c,
        learner_key=learner_key,
        decision_type="EXAM_SEED_STATE",
        entity_type="SEED",
        entity_id=reasoning_seed_id,
        environment=environment,
        inputs={"exam_rule_set_id": exam_rule_set_id, "authentic_count": len(authentic), "correct_count": len(correct), "fluent_count": len(fluent), "target_time": target},
        output={"state": state, "readiness_score": score, "fluency_state": fluency},
        ruleset_version=ruleset_version,
    )
    return {"reasoning_seed_id": reasoning_seed_id, "exam_rule_set_id": exam_rule_set_id, "state": state, "readiness_score": score, "fluency_state": fluency, "evidence_count": len(authentic)}


def confidence_calibration(c, learner_key: str, *, exam_rule_set_id: str = "", environment: str = ENV_LIVE, min_sample: int = MIN_CONFIDENCE_CALIBRATION_SAMPLE) -> dict[str, Any]:
    params: list[Any] = [learner_key, environment]
    clause = ""
    if exam_rule_set_id:
        clause = " AND exam_rule_set_id=?"
        params.append(exam_rule_set_id)
    rows = c.execute(
        f"SELECT confidence_band,is_correct FROM universal_response_events WHERE learner_key=? AND environment=? AND confidence_band<>'' {clause}",
        params,
    ).fetchall()
    if len(rows) < min_sample:
        return {"sample_count": len(rows), "calibrated": False, "descriptive_only": True, "bands": {}}
    groups: dict[str, list[int]] = {}
    for r in rows:
        groups.setdefault(r["confidence_band"], []).append(int(r["is_correct"] or 0))
    bands = {k: {"n": len(v), "accuracy": round(100.0 * sum(v) / len(v), 1)} for k, v in groups.items()}
    return {"sample_count": len(rows), "calibrated": True, "descriptive_only": True, "bands": bands}


def descriptive_attempt_ev(c, exam_rule_set_id: str, format_code: str, probability_correct: float) -> dict[str, Any]:
    rule = c.execute(
        "SELECT * FROM universal_exam_format_rules WHERE exam_rule_set_id=? AND format_code=? AND status='ACTIVE' ORDER BY section_code LIMIT 1",
        (exam_rule_set_id, format_code.upper()),
    ).fetchone()
    if not rule:
        raise ValueError("No exam format rule")
    p = min(1.0, max(0.0, float(probability_correct)))
    ev = p * float(rule["correct_marks"]) + (1 - p) * float(rule["wrong_marks"])
    return {"expected_value": round(ev, 4), "descriptive_only": True, "prescriptive_threshold": None, "rule_id": rule["exam_format_rule_id"]}


def record_exam_item_transition(c, *, learner_key: str, architecture_question_id: str, transition_type: str, attempt_id: int | None = None, old_response: str = "", new_response: str = "", occurred_at: str | None = None, environment: str = ENV_LIVE) -> str:
    tid = "UEX-" + hashlib.sha256(f"{learner_key}|{architecture_question_id}|{transition_type}|{attempt_id}|{old_response}|{new_response}|{occurred_at or utcnow()}".encode()).hexdigest()[:24]
    c.execute(
        """INSERT INTO universal_exam_item_transitions(
          transition_id,learner_key,attempt_id,architecture_question_id,transition_type,old_response,new_response,occurred_at,environment)
          VALUES(?,?,?,?,?,?,?,?,?)""",
        (tid, learner_key, attempt_id, architecture_question_id, transition_type.upper(), old_response, new_response, occurred_at or utcnow(), environment),
    )
    return tid


def record_full_exam_execution_opportunity(c, *, learner_key: str, exam_rule_set_id: str, attempt_id: int | None, component: str, estimated_loss: float | None, evidence_confidence: str, remediation_code: str, environment: str = ENV_LIVE, ruleset_version: str = DEFAULT_RULESET_VERSION) -> int:
    cur = c.execute(
        """INSERT INTO universal_full_exam_execution_state(
          learner_key,exam_rule_set_id,attempt_id,execution_component,estimated_loss,evidence_confidence,state,remediation_code,
          content_seed_attribution,ruleset_version,environment,created_at)
          VALUES(?,?,?,?,?,?,'OPEN',?,0.0,?,?,?)""",
        (learner_key, exam_rule_set_id, attempt_id, component.upper(), estimated_loss, evidence_confidence.upper(), remediation_code.upper(), ruleset_version, environment, utcnow()),
    )
    _log_decision(
        c,
        learner_key=learner_key,
        decision_type="EXECUTION_OPPORTUNITY",
        entity_type="FULL_EXAM",
        entity_id=exam_rule_set_id,
        environment=environment,
        inputs={"attempt_id": attempt_id, "component": component, "evidence_confidence": evidence_confidence},
        output={"estimated_loss": estimated_loss, "remediation_code": remediation_code, "content_seed_attribution": 0.0},
        ruleset_version=ruleset_version,
    )
    return int(cur.lastrowid)


def repair_cost_estimate(c, learner_key: str, entity_type: str, entity_id: str, content_complexity_band: str, *, min_observations: int = MIN_RECOVERY_OBSERVATIONS) -> dict[str, Any]:
    rows = c.execute(
        """SELECT observation_value FROM universal_repair_observations WHERE learner_key=? AND entity_type=? AND entity_id=?
          AND qualifying=1 AND observation_value IS NOT NULL ORDER BY observed_at""",
        (learner_key, entity_type.upper(), entity_id),
    ).fetchall()
    band = text(content_complexity_band).upper() or "MEDIUM"
    band_index = {"LOW": 0.8, "MEDIUM": 1.0, "HIGH": 1.3, "VERY_HIGH": 1.6}.get(band, 1.0)
    if len(rows) < int(min_observations):
        return {"source_state": "CONTENT_COMPLEXITY", "complexity_band": band, "repair_cost_index": band_index, "learner_specific": False, "precise_minutes": None, "observation_count": len(rows)}
    vals = [float(r["observation_value"]) for r in rows]
    mean = sum(vals) / len(vals)
    # Learner history phases in only after the configured qualifying gate.
    personalised = max(0.5, min(2.0, band_index * 0.5 + mean * 0.5))
    return {"source_state": "BLENDED_LEARNER_HISTORY", "complexity_band": band, "repair_cost_index": round(personalised, 3), "learner_specific": True, "precise_minutes": None, "observation_count": len(rows)}


def set_learner_goal(c, learner_key: str, exam_rule_set_id: str, goal_tier: str, target_score_objective: float | None, policy_version: str = "1") -> None:
    c.execute(
        """INSERT INTO universal_learner_goal_policy(
          learner_key,exam_rule_set_id,goal_tier,target_score_objective,policy_version,rank_promise_prohibited,updated_at)
          VALUES(?,?,?,?,?,1,?)
          ON CONFLICT(learner_key,exam_rule_set_id) DO UPDATE SET goal_tier=excluded.goal_tier,
          target_score_objective=excluded.target_score_objective,policy_version=excluded.policy_version,
          rank_promise_prohibited=1,updated_at=excluded.updated_at""",
        (learner_key, exam_rule_set_id, goal_tier.upper(), target_score_objective, policy_version, utcnow()),
    )


def compute_score_opportunity(
    c,
    *,
    learner_key: str,
    exam_rule_set_id: str,
    reasoning_seed_id: str,
    historical_exam_weight: float | None,
    current_expected_score: float | None,
    target_expected_score: float | None,
    unlock_factor: float = 1.0,
    retention_modifier: float = 1.0,
    repair_cost_index: float = 1.0,
    repair_cost_source_state: str = "CONTENT_COMPLEXITY",
    syllabus_compatibility: str = "CURRENT_COMPATIBLE",
    uncertainty: str = "MEDIUM",
    ruleset_version: str = DEFAULT_RULESET_VERSION,
) -> dict[str, Any]:
    compat = text(syllabus_compatibility).upper() or "UNKNOWN"
    if compat not in SYLLABUS_COMPATIBILITY:
        raise ValueError("Unsupported syllabus compatibility")
    current = None if current_expected_score is None else float(current_expected_score)
    target = None if target_expected_score is None else float(target_expected_score)
    weight = None if historical_exam_weight is None else max(0.0, float(historical_exam_weight))
    hist_conf = "UNRESOLVED" if compat == "SYLLABUS_NOVEL" or weight is None else uncertainty.upper()
    mar = None
    priority = None
    if compat != "OUTSIDE_CURRENT_SYLLABUS" and weight is not None and current is not None and target is not None:
        mar = weight * max(0.0, target - current)
        bounded_unlock = max(0.5, min(2.0, float(unlock_factor)))
        retention = max(0.5, min(2.0, float(retention_modifier)))
        repair = max(0.25, min(4.0, float(repair_cost_index)))
        priority = (mar * bounded_unlock * retention) / repair
    result = {
        "historical_exam_weight": weight,
        "historical_weight_confidence": hist_conf,
        "syllabus_compatibility": compat,
        "current_expected_score": current,
        "target_expected_score": target,
        "marks_at_risk": None if mar is None else round(mar, 4),
        "priority_score": None if priority is None else round(priority, 4),
        "novelty_protected": compat == "SYLLABUS_NOVEL",
    }
    c.execute(
        """INSERT INTO universal_score_opportunities(
          learner_key,exam_rule_set_id,reasoning_seed_id,historical_exam_weight,historical_weight_confidence,syllabus_compatibility,
          current_expected_score,target_expected_score,marks_at_risk,unlock_factor,retention_modifier,repair_cost_index,
          repair_cost_source_state,priority_score,uncertainty,ruleset_version,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(learner_key,exam_rule_set_id,reasoning_seed_id) DO UPDATE SET
          historical_exam_weight=excluded.historical_exam_weight,historical_weight_confidence=excluded.historical_weight_confidence,
          syllabus_compatibility=excluded.syllabus_compatibility,current_expected_score=excluded.current_expected_score,
          target_expected_score=excluded.target_expected_score,marks_at_risk=excluded.marks_at_risk,unlock_factor=excluded.unlock_factor,
          retention_modifier=excluded.retention_modifier,repair_cost_index=excluded.repair_cost_index,
          repair_cost_source_state=excluded.repair_cost_source_state,priority_score=excluded.priority_score,
          uncertainty=excluded.uncertainty,ruleset_version=excluded.ruleset_version,updated_at=excluded.updated_at""",
        (
            learner_key,
            exam_rule_set_id,
            reasoning_seed_id,
            weight,
            hist_conf,
            compat,
            current,
            target,
            result["marks_at_risk"],
            max(0.5, min(2.0, float(unlock_factor))),
            max(0.5, min(2.0, float(retention_modifier))),
            max(0.25, min(4.0, float(repair_cost_index))),
            repair_cost_source_state,
            result["priority_score"],
            uncertainty.upper(),
            ruleset_version,
            utcnow(),
        ),
    )
    return result


def validate_pyq_allocations(c, pyq_question_id: str) -> dict[str, Any]:
    rows = c.execute("SELECT * FROM universal_pyq_seed_map WHERE pyq_question_id=?", (pyq_question_id,)).fetchall()
    primary = [r for r in rows if text(r["mapping_role"]).upper() in {"PRIMARY", "SHARED_PRIMARY"}]
    total = sum(float(r["allocation_weight"] or 0) for r in primary)
    secondary_weight = sum(float(r["allocation_weight"] or 0) for r in rows if text(r["mapping_role"]).upper() not in {"PRIMARY", "SHARED_PRIMARY"})
    return {"valid": math.isclose(total, 1.0, abs_tol=1e-9) and math.isclose(secondary_weight, 0.0, abs_tol=1e-9), "primary_allocation": round(total, 6), "secondary_allocation": round(secondary_weight, 6), "mapping_count": len(rows)}


def emit_growth_event(c, event_type: str, user_key: str = "", payload: Mapping[str, Any] | None = None, occurred_at: str | None = None) -> str:
    if not feature_enabled(c, "growth_event_outbox"):
        return ""
    body = dict(payload or {})
    body.setdefault("source", "SCOREMAX")
    body.setdefault("scoremax_version", ENGINE_VERSION)
    body.setdefault("architecture_version", ARCHITECTURE_VERSION)
    event_time = occurred_at or utcnow()
    eid = "GE-" + hashlib.sha256(f"{event_type}|{user_key}|{event_time}|{canonical_json(body)}".encode()).hexdigest()[:24]
    c.execute(
        """INSERT OR IGNORE INTO universal_growth_event_outbox(event_id,event_type,user_key,occurred_at,payload_json,status,created_at)
          VALUES(?,?,?,?,?,'PENDING',?)""",
        (eid, event_type.upper(), user_key, event_time, canonical_json(body), utcnow()),
    )
    return eid


def capture_scoremax_attempt(c, *, attempt_id: int, assessment_session_id: int | None, student_id: int, meta: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Shadow-ingest an existing ScoreMax attempt when universal mapping exists.

    Unmapped legacy questions are intentionally skipped rather than inventing academic mappings.
    The legacy mastery engine remains authoritative during V6.3 internal-live testing.
    """
    learner = _learner_key(student_id)
    meta = dict(meta or {})
    market = text(meta.get("market") or ("PAKISTAN" if "FSc" in text(meta.get("programme")) else ""))
    if not feature_enabled(c, "universal_mastery_runtime", market=market, subject=text(meta.get("subject")), learner_key=learner):
        return {"enabled": False, "captured": 0, "skipped_unmapped": 0}
    rows = c.execute(
        """SELECT aa.*,q.question_id FROM attempt_answers aa JOIN questions q ON q.id=aa.question_db_id
          WHERE aa.attempt_id=? ORDER BY aa.id""",
        (attempt_id,),
    ).fetchall()
    captured = skipped = 0
    results = []
    for r in rows:
        qarch = _question_architecture(c, question_db_id=r["question_db_id"])
        if not qarch:
            skipped += 1
            continue
        confidence = text(r["confidence"] if "confidence" in r.keys() else "")
        response_seconds = int(r["response_time_seconds"] or 0) if "response_time_seconds" in r.keys() else 0
        result = record_response_event(
            c,
            learner_key=learner,
            question_db_id=r["question_db_id"],
            response_text=text(r["selected_answer"]),
            is_correct=bool(r["is_correct"]),
            marks_awarded=float(r["marks_awarded"] or 0) if "marks_awarded" in r.keys() else float(r["is_correct"] or 0),
            attempt_id=attempt_id,
            assessment_session_id=assessment_session_id,
            active_duration_seconds=response_seconds,
            confidence_band=confidence,
            assistance_state="UNASSISTED",
            delivery_context=("AUTHENTIC_EXAM" if text(meta.get("assessment_kind")).lower() == "mock" else text(qarch["delivery_context"])),
            environment=ENV_LIVE,
        )
        captured += 1
        results.append(result)
    emit_growth_event(c, "ASSESSMENT_COMPLETED", learner, {"attempt_id": attempt_id, "subject": meta.get("subject", ""), "assessment_kind": meta.get("assessment_kind", ""), "universal_events": captured})
    return {"enabled": True, "captured": captured, "skipped_unmapped": skipped, "results": results}


def universal_recovery_actions(c, student_id: int, *, limit: int = 6, environment: str = ENV_LIVE) -> list[dict[str, Any]]:
    learner = _learner_key(student_id)
    rows = c.execute(
        """SELECT * FROM universal_recovery_queue WHERE learner_key=? AND status='OPEN' AND environment=?
          ORDER BY priority,due_at,created_at LIMIT ?""",
        (learner, environment, int(limit)),
    ).fetchall()
    out = []
    for r in rows:
        label = r["entity_id"]
        if r["entity_type"] == "FAMILY":
            x = c.execute("SELECT title,subject,chapter FROM universal_claim_families WHERE claim_family_id=?", (r["entity_id"],)).fetchone()
        elif r["entity_type"] == "NODE":
            x = c.execute("SELECT claim AS title,subject,chapter FROM universal_knowledge_nodes WHERE knowledge_node_id=?", (r["entity_id"],)).fetchone()
        else:
            x = c.execute("SELECT title,subject,chapter FROM universal_reasoning_seeds WHERE reasoning_seed_id=?", (r["entity_id"],)).fetchone()
        if x:
            label = x["title"]
        out.append({**dict(r), "label": label, "subject": x["subject"] if x else "", "chapter": x["chapter"] if x else ""})
    return out


def universal_maintenance_actions(c, student_id: int, *, limit: int = 6, environment: str = ENV_LIVE) -> list[dict[str, Any]]:
    learner = _learner_key(student_id)
    rows = c.execute(
        """SELECT * FROM universal_maintenance_queue WHERE learner_key=? AND status='OPEN' AND environment=?
          ORDER BY due_at LIMIT ?""",
        (learner, environment, int(limit)),
    ).fetchall()
    out = []
    for r in rows:
        label = r["entity_id"]
        if r["entity_type"] == "FAMILY":
            x = c.execute("SELECT title,subject,chapter FROM universal_claim_families WHERE claim_family_id=?", (r["entity_id"],)).fetchone()
        elif r["entity_type"] == "NODE":
            x = c.execute("SELECT claim AS title,subject,chapter FROM universal_knowledge_nodes WHERE knowledge_node_id=?", (r["entity_id"],)).fetchone()
        else:
            x = c.execute("SELECT title,subject,chapter FROM universal_reasoning_seeds WHERE reasoning_seed_id=?", (r["entity_id"],)).fetchone()
        if x:
            label = x["title"]
        out.append({**dict(r), "label": label, "subject": x["subject"] if x else "", "chapter": x["chapter"] if x else ""})
    return out


def learner_snapshot(c, student_id: int | str, *, environment: str = ENV_LIVE) -> dict[str, Any]:
    learner = _learner_key(student_id) if not text(student_id).startswith("QA:") else text(student_id)
    env = _environment(environment)
    def states(table):
        rows = c.execute(f"SELECT state,COUNT(*) n FROM {table} WHERE learner_key=? AND environment=? GROUP BY state", (learner, env)).fetchall()
        return {r["state"]: int(r["n"]) for r in rows}
    return {
        "learner_key": learner,
        "environment": env,
        "knowledge": states("universal_learner_node_state"),
        "claim_families": states("universal_learner_family_state"),
        "reasoning": states("universal_learner_seed_state"),
        "open_recovery": c.execute("SELECT COUNT(*) n FROM universal_recovery_queue WHERE learner_key=? AND environment=? AND status='OPEN'", (learner, env)).fetchone()["n"],
        "maintenance_due": c.execute("SELECT COUNT(*) n FROM universal_maintenance_queue WHERE learner_key=? AND environment=? AND status='OPEN'", (learner, env)).fetchone()["n"],
        "response_events": c.execute("SELECT COUNT(*) n FROM universal_response_events WHERE learner_key=? AND environment=?", (learner, env)).fetchone()["n"],
    }


def runtime_status(c) -> dict[str, Any]:
    arch = c.execute("SELECT * FROM universal_architecture_versions WHERE architecture_version=?", (ARCHITECTURE_VERSION,)).fetchone()
    return {
        "scoremax_version": ENGINE_VERSION,
        "architecture_version": ARCHITECTURE_VERSION,
        "governance_reference_version": GOVERNANCE_REFERENCE_VERSION,
        "ruleset_version": DEFAULT_RULESET_VERSION,
        "requirements": {"range": arch["requirement_range"] if arch else "SM-001..SM-069", "count": arch["requirement_count"] if arch else 69, "p0": arch["p0_count"] if arch else 39},
        "feature_flags": [dict(r) for r in c.execute("SELECT feature_code,scope_type,scope_key,enabled,mode FROM universal_feature_flags ORDER BY feature_code,scope_type,scope_key").fetchall()],
        "counts": {
            "claim_families": c.execute("SELECT COUNT(*) n FROM universal_claim_families").fetchone()["n"],
            "knowledge_nodes": c.execute("SELECT COUNT(*) n FROM universal_knowledge_nodes").fetchone()["n"],
            "reasoning_seeds": c.execute("SELECT COUNT(*) n FROM universal_reasoning_seeds").fetchone()["n"],
            "mandatory_gates": c.execute("SELECT COUNT(*) n FROM universal_claim_family_gates WHERE required=1").fetchone()["n"],
            "question_mappings": c.execute("SELECT COUNT(*) n FROM universal_question_architecture").fetchone()["n"],
            "live_response_events": c.execute("SELECT COUNT(*) n FROM universal_response_events WHERE environment='LIVE'").fetchone()["n"],
            "qa_response_events": c.execute("SELECT COUNT(*) n FROM universal_response_events WHERE environment='QA_SANDBOX_ONLY'").fetchone()["n"],
            "growth_outbox_pending": c.execute("SELECT COUNT(*) n FROM universal_growth_event_outbox WHERE status='PENDING'").fetchone()["n"],
        },
        "legacy_mastery_authoritative": True,
        "reviewer_workspace_forward_dependency": False,
    }


def load_synthetic_laws_of_motion_shape_fixture(c, *, environment: str = ENV_QA) -> dict[str, int]:
    """Load a non-academic QA fixture matching the governed Laws-of-Motion object counts.

    The fixture intentionally contains generic placeholder claims. It tests software cardinality,
    FK/gate/state behaviour only; it is never student-released and is not valid academic content.
    """
    env = _environment(environment)
    if env != ENV_QA:
        raise ValueError("Synthetic shape fixture is QA_SANDBOX_ONLY")
    # 52 families; 48 subject-weight; 42 exam-weight. The last four are source-only/support families.
    for i in range(1, 53):
        upsert_claim_family(
            c,
            {
                "claim_family_id": f"QA-LOM-CF-{i:03d}",
                "subject": "Physics",
                "chapter": "Laws of Motion",
                "title": f"QA Laws-of-Motion Claim Family {i}",
                "subject_role": "CORE" if i <= 48 else "SUPPORTING",
                "exam_role": "ELIGIBLE" if i <= 42 else "SUPPORTING",
                "independent_weight": 1.0 if i <= 48 else 0.0,
                "closure_policy": DEFAULT_FAMILY_POLICY,
                "environment": env,
                "status": "QA_ONLY",
            },
        )
    # Exactly 195 nodes: 153 DIRECT, 38 SUPPORTING, 4 SOURCE_ONLY.
    for i in range(1, 196):
        role = "DIRECT" if i <= 153 else ("SUPPORTING" if i <= 191 else "SOURCE_ONLY")
        fid = f"QA-LOM-CF-{((i - 1) % 52) + 1:03d}"
        upsert_knowledge_node(
            c,
            {
                "knowledge_node_id": f"QA-LOM-KN-{i:03d}",
                "claim_family_id": fid,
                "subject": "Physics",
                "chapter": "Laws of Motion",
                "claim": f"QA shape node {i}; not academic content",
                "source_role": role,
                "exam_mastery_eligible": role != "SOURCE_ONLY",
                "environment": env,
                "status": "QA_ONLY",
            },
        )
    for i in range(1, 39):
        upsert_reasoning_seed(
            c,
            {
                "reasoning_seed_id": f"QA-LOM-RS-{i:03d}",
                "subject": "Physics",
                "chapter": "Laws of Motion",
                "title": f"QA reasoning seed {i}",
                "decisive_operation": f"QA decisive operation {i}; not academic content",
                "independent_weight": 1.0,
                "environment": env,
                "status": "QA_ONLY",
            },
        )
    # Attach nodes to seeds only to exercise many-to-many structure.
    for i in range(1, 196):
        map_node_seed(c, f"QA-LOM-KN-{i:03d}", f"QA-LOM-RS-{((i - 1) % 38) + 1:03d}", mapping_role="PRIMARY" if i <= 38 else "SECONDARY", governance_status="QA_ONLY")
    # 29 mandatory gates, each tied to a distinct node/family mapping.
    for i in range(1, 30):
        nid = f"QA-LOM-KN-{i:03d}"
        node = c.execute("SELECT claim_family_id FROM universal_knowledge_nodes WHERE knowledge_node_id=?", (nid,)).fetchone()
        upsert_claim_family_gate(
            c,
            {
                "gate_id": f"QA-LOM-MG-{i:03d}",
                "claim_family_id": node["claim_family_id"],
                "knowledge_node_id": nid,
                "gate_type": "MISCONCEPTION_GUARD" if i % 3 == 0 else "REQUIRED_CORRECT",
                "required": True,
                "closure_effect": "REOPEN" if i % 3 == 0 else "BLOCK",
                "environment": env,
                "status": "ACTIVE",
            },
        )
    # 10 prerequisite controls.
    for i in range(1, 11):
        upsert_prerequisite_edge(
            c,
            {
                "prerequisite_edge_id": f"QA-LOM-PR-{i:02d}",
                "from_entity_type": "NODE",
                "from_entity_id": f"QA-LOM-KN-{i:03d}",
                "to_entity_type": "NODE",
                "to_entity_id": f"QA-LOM-KN-{i + 20:03d}",
                "strength": "HIGH" if i <= 3 else "MEDIUM",
                "environment": env,
                "status": "QA_ONLY",
            },
        )
    # 76 NEET/JEE profiles (38 * 2), not academic calibration.
    for i in range(1, 39):
        sid = f"QA-LOM-RS-{i:03d}"
        upsert_exam_seed_profile(c, {"reasoning_seed_id": sid, "exam_rule_set_id": "IND-NEET-2026-v1", "authentic_formats": ["MCQ_SINGLE"], "target_time_seconds": 60, "time_target_status": "INTERNAL", "mastery_policy": {"min_authentic_events": 2, "min_accuracy": 70, "require_fluency": True}, "status": "QA_ONLY"})
        upsert_exam_seed_profile(c, {"reasoning_seed_id": sid, "exam_rule_set_id": "IND-JEE-2026-v1", "authentic_formats": ["MCQ_SINGLE", "NUMERICAL_VALUE"], "target_time_seconds": 90, "time_target_status": "INTERNAL", "mastery_policy": {"min_authentic_events": 2, "min_accuracy": 70, "require_fluency": True}, "status": "QA_ONLY"})
    return {
        "knowledge_nodes": 195,
        "claim_families": 52,
        "independent_subject_weight_families": 48,
        "exam_weight_families": 42,
        "reasoning_seeds": 38,
        "mandatory_gates": 29,
        "prerequisite_controls": 10,
        "exam_seed_profiles": 76,
    }


def qa_fixture_counts(c) -> dict[str, int]:
    return {
        "knowledge_nodes": c.execute("SELECT COUNT(*) n FROM universal_knowledge_nodes WHERE environment=?", (ENV_QA,)).fetchone()["n"],
        "claim_families": c.execute("SELECT COUNT(*) n FROM universal_claim_families WHERE environment=?", (ENV_QA,)).fetchone()["n"],
        "reasoning_seeds": c.execute("SELECT COUNT(*) n FROM universal_reasoning_seeds WHERE environment=?", (ENV_QA,)).fetchone()["n"],
        "mandatory_gates": c.execute("SELECT COUNT(*) n FROM universal_claim_family_gates WHERE environment=? AND required=1", (ENV_QA,)).fetchone()["n"],
        "prerequisite_controls": c.execute("SELECT COUNT(*) n FROM universal_prerequisite_edges WHERE environment=?", (ENV_QA,)).fetchone()["n"],
        "exam_seed_profiles": c.execute("SELECT COUNT(*) n FROM universal_exam_seed_profiles WHERE reasoning_seed_id LIKE 'QA-LOM-RS-%'").fetchone()["n"],
    }
