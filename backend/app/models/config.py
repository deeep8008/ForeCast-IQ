"""
Centralized Configuration for Statistical Forecasting Models (Phase 4)
ForecastIQ Backend
"""
from typing import Dict, Any, Tuple


class ModelDefaults:
    # ARIMA standard defaults
    ARIMA_P: int = 1
    ARIMA_D: int = 1
    ARIMA_Q: int = 1

    # SARIMA seasonal defaults (weekly seasonality for daily enterprise sales)
    SARIMA_ORDER: Tuple[int, int, int] = (1, 1, 1)
    SARIMA_SEASONAL_ORDER: Tuple[int, int, int, int] = (1, 0, 1, 7)

    # Prophet defaults
    PROPHET_YEARLY_SEASONALITY: bool = False
    PROPHET_WEEKLY_SEASONALITY: bool = True
    PROPHET_DAILY_SEASONALITY: bool = False
    PROPHET_INTERVAL_WIDTH: float = 0.95

    # LightGBM defaults
    LGBM_N_ESTIMATORS: int = 100
    LGBM_LEARNING_RATE: float = 0.05
    LGBM_NUM_LEAVES: int = 31
    LGBM_MAX_DEPTH: int = -1
    LGBM_SUBSAMPLE: float = 0.8
    LGBM_RANDOM_STATE: int = 42

    # DeepAR defaults (Darts RNNModel with GaussianLikelihood)
    DEEPAR_INPUT_CHUNK_LENGTH: int = 14
    DEEPAR_TRAINING_LENGTH: int = 28
    DEEPAR_EPOCHS: int = 15
    DEEPAR_BATCH_SIZE: int = 16
    DEEPAR_HIDDEN_DIM: int = 20
    DEEPAR_NUM_LAYERS: int = 2
    DEEPAR_DROPOUT: float = 0.1
    DEEPAR_RANDOM_STATE: int = 42
    DEEPAR_NUM_SAMPLES: int = 100

    # TFT defaults (Darts TFTModel)
    TFT_INPUT_CHUNK_LENGTH: int = 14
    TFT_OUTPUT_CHUNK_LENGTH: int = 7
    TFT_EPOCHS: int = 15
    TFT_BATCH_SIZE: int = 16
    TFT_HIDDEN_SIZE: int = 16
    TFT_LSTM_LAYERS: int = 1
    TFT_ATTENTION_HEADS: int = 2
    TFT_DROPOUT: float = 0.1
    TFT_RANDOM_STATE: int = 42

    # Horizon options
    SUPPORTED_HORIZONS = [7, 28, 90]

    # Minimum history requirements
    MIN_OBSERVATIONS = {
        7: 14,
        28: 35,
        90: 100,
    }

