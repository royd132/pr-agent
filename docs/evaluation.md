# Evaluation and evidence limits

## Synthetic Fault Benchmark v1

`evaluation_data/pr_diff_100.jsonl` is a deterministic offline fixture supplied for this repository. It contains:

- 100 cases across 10 fictional repositories;
- 80 validation cases and 20 repository-disjoint holdout cases;
- 40 positive cases, 60 clean cases and 40 expected findings;
- 21 rule IDs;
- severity distribution: 4 critical, 15 high, 16 medium and 5 low;
- file SHA-256 `65F301C0C75125676D5DA482FFA00828399B7041D4DB378BC52E48BAAB36B1B6`.

The corpus is **not real public PR data**. It has no train split and cannot establish production accuracy, ecosystem coverage or reviewer acceptance. Its purpose is regression detection, deterministic demonstrations and evaluation-pipeline verification.

## Data split policy

Splits are repository-disjoint. Validation may be used to compare candidates. Holdout is locked for the promotion decision and should not be inspected during candidate construction. A future production claim additionally requires a documented, licensed, representative public-PR or consented private-PR dataset with a train/validation/holdout policy.

## Public arms

| Internal key | Public label | Purpose |
|---|---|---|
| `single-model` / `single-llm` | Solo Review | Model baseline |
| `multi-llm-no-critic` | Prism without Examiner | Isolate evidence-examination value |
| `full-agentic` | Full DiffPrism | Four-stage protocol |

Internal keys remain stable for historical run compatibility.

## Metrics

Primary metrics are finding precision, recall and F1, high-risk recall, clean accuracy, exact-line accuracy, evidence accuracy, invalid comments per PR, p95 review latency and cost per verified finding. Runtime records also retain model calls, tokens, total cost, failures and examiner accept/reject counts.

One-to-one matching prevents duplicate predictions from receiving duplicate credit. CWE is used as the canonical category when available; reviewer-specific rule IDs are not assumed globally stable.

## Promotion gate

A candidate can be activated only when it meets the configured validation improvement, does not regress protected metrics, passes the locked holdout, and leaves a reproducible record containing dataset fingerprint, prompt/Skill version, configuration, cost and latency. Offline fixtures always set `production_activation_allowed` to false.

## Reproduce

```powershell
python scripts/run_accuracy_experiment.py
python scripts/run_agentic_evaluation.py
python scripts/run_controlled_experiments.py
python scripts/run_prompt_evolution_proof.py
```

Do not publish a score without recording the exact command, git commit, model/provider, configuration, dataset hashes, raw result artifact and execution date. A result from this synthetic fixture must be labelled synthetic.
