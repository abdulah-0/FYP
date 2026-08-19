"""
Training script for Sensor Risk Classifier.
Trains Random Forest and Gradient Boosting models, evaluates performance,
and saves the best model artifact to packages/ml-classifier/model/.
"""

import json
import os
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from preprocess import FEATURE_COLUMNS, RISK_TIERS, prepare_and_save_dataset


def train_sensor_model(
    data_path: str = "data/processed/forest_fire_processed.csv",
    model_output_dir: str = "packages/ml-classifier/model",
    random_state: int = 42
):
    """
    Trains and evaluates multi-tier sensor classification models.
    """
    if not os.path.exists(data_path):
        raw_path = "data/raw/Algerian_forest_fires_dataset.csv"
        prepare_and_save_dataset(raw_path, data_path)

    df = pd.read_csv(data_path)
    X = df[FEATURE_COLUMNS]
    y = df["Risk_Tier"]

    # Stratified Train/Test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=random_state, stratify=y
    )

    models = {
        "RandomForest": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(
                n_estimators=150,
                max_depth=8,
                min_samples_split=3,
                random_state=random_state,
                class_weight="balanced"
            ))
        ]),
        "GradientBoosting": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=4,
                random_state=random_state
            ))
        ])
    }

    best_name = None
    best_score = -1.0
    best_pipeline = None
    results = {}

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state)

    for name, pipeline in models.items():
        cv_scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="f1_macro")
        pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)
        
        test_f1 = f1_score(y_test, y_pred, average="macro")
        test_acc = pipeline.score(X_test, y_test)
        test_prec = precision_score(y_test, y_pred, average="macro", zero_division=0)
        test_rec = recall_score(y_test, y_pred, average="macro", zero_division=0)

        results[name] = {
            "cv_f1_macro_mean": float(np.mean(cv_scores)),
            "cv_f1_macro_std": float(np.std(cv_scores)),
            "test_accuracy": float(test_acc),
            "test_f1_macro": float(test_f1),
            "test_precision_macro": float(test_prec),
            "test_recall_macro": float(test_rec),
            "classification_report": classification_report(y_test, y_pred, target_names=[RISK_TIERS[i] for i in sorted(RISK_TIERS.keys())], output_dict=True),
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist()
        }

        print(f"\n================ Model: {name} ================")
        print(f"5-Fold CV F1-Macro: {np.mean(cv_scores):.4f} +/- {np.std(cv_scores):.4f}")
        print(f"Test Accuracy: {test_acc:.4f} | Test F1-Macro: {test_f1:.4f}")
        print("Classification Report:")
        print(classification_report(y_test, y_pred, target_names=[RISK_TIERS[i] for i in sorted(RISK_TIERS.keys())]))

        if test_f1 > best_score:
            best_score = test_f1
            best_name = name
            best_pipeline = pipeline

    # Save model and metadata
    output_dir = Path(model_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    model_path = output_dir / "sensor_classifier.joblib"
    joblib.dump(best_pipeline, model_path)

    metadata = {
        "best_model_name": best_name,
        "feature_columns": FEATURE_COLUMNS,
        "risk_tiers": RISK_TIERS,
        "metrics": results[best_name],
        "all_model_results": results
    }

    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n>>> Best Model: {best_name} (F1-Macro: {best_score:.4f})")
    print(f">>> Saved pipeline to {model_path}")
    print(f">>> Saved metadata to {metadata_path}")
    return best_pipeline, metadata


if __name__ == "__main__":
    train_sensor_model()
