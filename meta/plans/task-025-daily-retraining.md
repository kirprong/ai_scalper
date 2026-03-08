---
SECTION_ID: plans.task-025-daily-retraining
TYPE: plan
STATUS: completed
PRIORITY: medium
---

# TASK-025: Evolution - Daily Re-training Pipeline

GOAL: Автоматический пайплайн дообучения моделей при падении точности ниже 75%
TIMELINE: 1 session

## Task Checklist

### Phase 1: Core Retraining Logic
- [x] Create `backend/evolution/__init__.py` - Module initialization
- [x] Create `backend/evolution/daily_retraining.py` - Main retraining pipeline
- [x] Implement accuracy check logic (check yesterday's predictions)
- [x] Implement fine-tuning trigger (< 75% accuracy)
- [x] Implement 48h data fetching for retraining

### Phase 2: Model Versioning
- [x] Create `backend/evolution/model_versioning.py` - Model version management
- [x] Implement model backup before retraining
- [x] Implement model rollback on failure
- [x] Track model versions with metadata

### Phase 3: Testing & Validation
- [x] Create `backend/evolution/test_daily_retraining.py` - Unit tests
- [x] Create `backend/evolution/test_model_versioning.py` - Unit tests
- [x] Test: accuracy < 75% triggers retraining
- [x] Test: model versioning works correctly
- [x] Update tasks.json status to done

## Success Criteria
- [x] Accuracy check implemented
- [x] Fine-tuning triggered when accuracy < 75%
- [x] 48h data fetching working
- [x] Model versioning implemented
- [x] All tests pass

## Technical Requirements

### Accuracy Check:
- Query yesterday's predictions from ClickHouse
- Compare predicted vs actual outcomes
- Calculate accuracy: correct_predictions / total_predictions

### Fine-tuning Trigger:
- If accuracy < 0.75 (75%):
  - Fetch last 48 hours of labeled data
  - Run fine-tuning on LSTM and XGBoost
  - Save new model version

### Model Versioning:
- Backup current model before retraining
- Version format: `model_timestamp_v{version}.pt`
- Metadata: accuracy, training_date, data_range

## Dependencies
- TASK-024 ✅ (Telemetry)
- TASK-011 ✅ (LSTM Model)
