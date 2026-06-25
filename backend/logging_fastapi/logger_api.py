import logging
from src.utils.logger import CustomLogger,create_log_path

prediction_logger = CustomLogger(
    logger_name="prediction",
    log_filename=create_log_path("Prediction")
)

prediction_logger.set_log_level(level=logging.INFO)

auth_logger = CustomLogger(
    logger_name="auth",
    log_filename=create_log_path("Auth")
)

auth_logger.set_log_level(level=logging.INFO)

health_logger = CustomLogger(
    logger_name="health",
    log_filename=create_log_path("Health")
)

health_logger.set_log_level(level=logging.INFO)