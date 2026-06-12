import json

from app.corporate_authorship_detector import CorporateAuthorshipDetector


def test_detector_scores_xgboost_json_model(tmp_path):
    model_path = tmp_path / "xgb_model.json"
    metadata_path = tmp_path / "xgb_model_metadata.json"
    edge_path = tmp_path / "edge.json"
    model_path.write_text(
        json.dumps(
            {
                "learner": {
                    "learner_model_param": {"base_score": "[5E-1]"},
                    "gradient_booster": {
                        "model": {
                            "trees": [
                                {
                                    "left_children": [1, -1, -1],
                                    "right_children": [2, -1, -1],
                                    "default_left": [1, 0, 0],
                                    "split_indices": [0, 0, 0],
                                    "split_conditions": [0.5, -2.0, 2.0],
                                    "base_weights": [0.0, -2.0, 2.0],
                                }
                            ]
                        }
                    },
                },
                "version": [3, 2, 0],
            }
        ),
        encoding="utf-8",
    )
    metadata_path.write_text(
        json.dumps(
            {
                "trainer": "xgboost",
                "method": "lexical_shape_xgboost",
                "vocab": ["lex::1=synergy"],
                "feature_importance": {"by_gain": [{"feature": "lex::1=synergy", "gain": 10.0}]},
            }
        ),
        encoding="utf-8",
    )
    edge_path.write_text(
        json.dumps(
            {
                "modelVersion": "xgb-json-test-model",
                "trainer": "xgboost",
                "primaryMethod": "lexical_shape_xgboost",
                "decisionPolicy": {"threshold": 0.6},
            }
        ),
        encoding="utf-8",
    )

    detector = CorporateAuthorshipDetector(
        model_path=model_path,
        edge_artifact_path=edge_path,
        train_path=tmp_path / "missing.jsonl",
    )

    result = detector.score("synergy")

    assert result["available"] is True
    assert result["trainer"] == "xgboost"
    assert result["model_id"] == "xgb-json-test-model"
    assert result["label"] == "ai_generated"
    assert result["likelihood"] == 88
    assert result["top_features"][0]["feature"] == "lex::1=synergy"
    assert result["top_features"][0]["importance_gain"] == 10.0
