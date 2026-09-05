# ADR-006: Scoped ML tools, not a fraud decision agent

Status: accepted

## Decision
Classification and regression are separate catalog tasks. `select_ml_task` chooses `classification`, `regression`, `both`, `descriptive`, or `none`. The graph may use a model score as evidence. The writer must not treat it as a fraud decision or invent holdout metrics.

- Classification (`score_risk`): logistic P(failed) on leakage-safe payment features.
- Regression (`score_regression`): Ridge on capture latency (`captured_at − created_at`) for succeeded payments.
- Descriptive questions (success rate, health, volume) skip ML.

Insufficient training data raises `InsufficientTrainingData` (API 422). No dummy accuracy, AUC, MAE, or R².

## Why
Payment features already exist on `payments`. A classifier that outputs P(failure) is useful if it *triggers* investigation. Mixing expected-loss RMSE into a classifier quality blob overclaims. Synthetic capture times are nearly constant, so a low R² is honest.

## Evaluation
Classification holdout: accuracy, precision, recall, F1 (failed class), confusion matrix, ROC-AUC (None if one class is missing). Regression holdout: MAE, RMSE, R². Version the dataset and model. Do not combine the two quality objects.
