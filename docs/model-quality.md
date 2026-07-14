# Model and Alert Quality

SignalChord is not approved to run production model or alert-quality decisions on real customer data yet. Repository evidence is limited to synthetic fixtures and control gates that prevent missing quality evidence from passing unnoticed.

## Intended and Prohibited Use

The intended use is analyst-facing news intelligence: source-attributed extraction, entity and claim organization, configurable alert prioritization, and provenance tracing. SignalChord outputs are decision support and require visible evidence.

Prohibited uses are listed in `quality/evaluation-plan.json` and include fully automated adverse decisions about people, unreviewed publication of sensitive allegations as verified fact, regulated eligibility decisions, identity verification, and biometric inference.

## Evaluation Assets

- Evaluation plan: `quality/evaluation-plan.json`
- Repository-owned synthetic dataset: `quality/datasets/synthetic-fixture-v1.json`
- Repository baseline result: `quality/results/repository-baseline.json`
- Validator and regression tests: `scripts/validate_quality.py`, `scripts/test_validate_quality.py`

These assets are deliberately marked as repository controls, not production approval. They prove the evaluation contract, thresholds, coverage requirements, review rules, and failure behavior can be validated in CI.

## Critical Stages

The release candidate must report metrics for extraction, entity resolution, claim linking, and alert quality. Each stage has threshold metrics and regression budgets in `quality/evaluation-plan.json`.

Release validation must fail if any critical metric falls below threshold, if regression budgets are exceeded, or if the result claims production approval without the required external evidence.

## Human Review and Abstention

High-risk cases require human review before verified labels or external high-severity notifications. Low-confidence entity resolution must abstain from model-verified status and route to review. Low-confidence claims must not trigger high-severity alerts without corroborating evidence.

The current deterministic entity resolver already exposes `requires_review`; production model adapters must preserve that contract and add segmented metrics for review-routing recall.

## Coverage and Failure Modes

The repository dataset covers only English synthetic examples across technology, regulatory, and supply-chain scenarios. It does not represent real licensed sources, multilingual inputs, geography, demographics, noisy/adversarial text, or source-specific bias.

Production approval requires a representative evaluation report with:

- legally usable datasets and train/test separation;
- annotation guidance and inter-annotator or QA evidence;
- model, rule, policy, and configuration identifiers;
- segmented metrics by source type, language, domain, and risk level;
- false-positive and false-negative budget approval;
- error analysis for bias, drift, adversarial/noisy input, and source concentration;
- rollback criteria tied to production feedback and quality proxy monitoring.

## Monitoring and Rollback

Production monitoring must track alert relevance feedback, false-positive rate by source, entity-resolution review rate, claim dispute rate, source/language drift, and suppressed high-score alert counts.

Rollback is required if critical release-candidate metrics miss threshold, precision regressions exceed budget, high-risk review-routing recall drops below threshold, or production feedback shows sustained false-positive rates above the approved budget.
