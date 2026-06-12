from run_authorship_corpus_v2_markov_everything import defensive_calibration_split, evaluate_operating_target, threshold_metrics


def test_defensive_calibration_split_is_label_balanced_and_deterministic():
    rows = [
        {
            "doc_id": f"human_{idx}",
            "source_type": "human_written",
            "ai_generated_label": 0,
            "text": f"Human calibration text {idx}",
        }
        for idx in range(8)
    ] + [
        {
            "doc_id": f"ai_{idx}",
            "source_type": "ai_generated",
            "ai_generated_label": 1,
            "text": f"AI calibration text {idx}",
        }
        for idx in range(8)
    ]

    first_train, first_holdout, first_summary = defensive_calibration_split(
        rows,
        train_ratio=0.25,
        max_train_per_label=0,
        source_name="calibration_hc3_wiki",
    )
    second_train, second_holdout, second_summary = defensive_calibration_split(
        list(reversed(rows)),
        train_ratio=0.25,
        max_train_per_label=0,
        source_name="calibration_hc3_wiki",
    )

    assert first_summary["train_label_counts"] == {"human_written": 2, "ai_generated": 2}
    assert first_summary["holdout_label_counts"] == {"human_written": 6, "ai_generated": 6}
    assert {row["doc_id"] for row in first_train} == {row["doc_id"] for row in second_train}
    assert {row["doc_id"] for row in first_holdout} == {row["doc_id"] for row in second_holdout}
    assert not ({row["doc_id"] for row in first_train} & {row["doc_id"] for row in first_holdout})
    assert second_summary == first_summary


def test_defensive_calibration_split_honors_per_label_cap():
    rows = [
        {
            "doc_id": f"human_{idx}",
            "source_type": "human_written",
            "ai_generated_label": 0,
            "text": f"Human calibration text {idx}",
        }
        for idx in range(10)
    ] + [
        {
            "doc_id": f"ai_{idx}",
            "source_type": "ai_generated",
            "ai_generated_label": 1,
            "text": f"AI calibration text {idx}",
        }
        for idx in range(10)
    ]

    train, holdout, summary = defensive_calibration_split(
        rows,
        train_ratio=0.9,
        max_train_per_label=3,
        source_name="calibration_hc3_qa",
    )

    assert summary["train_label_counts"] == {"human_written": 3, "ai_generated": 3}
    assert summary["holdout_label_counts"] == {"human_written": 7, "ai_generated": 7}
    assert len(train) == 6
    assert len(holdout) == 14


def test_threshold_metrics_reports_false_positive_tradeoff_counts():
    predictions = [
        {"actual": "human_written", "ai_generated_probability": 0.81},
        {"actual": "human_written", "ai_generated_probability": 0.31},
        {"actual": "ai_generated", "ai_generated_probability": 0.91},
        {"actual": "ai_generated", "ai_generated_probability": 0.61},
    ]

    low, high = threshold_metrics(predictions, [0.6, 0.8])

    assert low["human_false_positive_count"] == 1
    assert low["ai_false_negative_count"] == 0
    assert low["human_false_positive_rate"] == 0.5
    assert low["ai_recall"] == 1.0

    assert high["human_false_positive_count"] == 1
    assert high["ai_false_negative_count"] == 1
    assert high["human_true_negative_count"] == 1
    assert high["ai_true_positive_count"] == 1
    assert high["false_positive_weighted_cost"] > low["false_positive_weighted_cost"]


def test_operating_target_requires_ai_recall_above_80_and_human_fpr_below_20():
    result = {
        "method": "lexical_shape_plus_markov",
        "splits": {
            "supervised_test": {
                "threshold_sweep": [{"threshold": 0.6, "accuracy": 0.9, "ai_recall": 0.95, "human_false_positive_rate": 0.05}]
            },
            "calibration_hc3_wiki": {
                "threshold_sweep": [{"threshold": 0.6, "accuracy": 0.88, "ai_recall": 0.81, "human_false_positive_rate": 0.19}]
            },
            "calibration_hc3_qa": {
                "threshold_sweep": [{"threshold": 0.6, "accuracy": 0.87, "ai_recall": 0.79, "human_false_positive_rate": 0.08}]
            },
        },
    }

    failed = evaluate_operating_target(result, 0.6)
    assert failed["minimum_ai_recall"] == 0.8
    assert failed["minimum_ai_recall_comparison"] == ">"
    assert failed["maximum_human_false_positive_rate"] == 0.2
    assert failed["maximum_human_false_positive_rate_comparison"] == "<"
    assert failed["splits"]["calibration_hc3_qa"]["passed"] is False
    assert failed["passed"] is False

    result["splits"]["calibration_hc3_qa"]["threshold_sweep"][0]["ai_recall"] = 0.8
    boundary = evaluate_operating_target(result, 0.6)
    assert boundary["splits"]["calibration_hc3_qa"]["passed"] is False
    assert boundary["passed"] is False

    result["splits"]["calibration_hc3_qa"]["threshold_sweep"][0]["ai_recall"] = 0.8001
    passed = evaluate_operating_target(result, 0.6)
    assert passed["splits"]["calibration_hc3_qa"]["passed"] is True
    assert passed["passed"] is True
