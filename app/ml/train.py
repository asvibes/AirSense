from collections import defaultdict
from pathlib import Path

from sqlalchemy import select

from app.db import get_session
from app.main import create_app
from app.ml.forecasting import evaluate_and_fit, save_models
from app.models.reading import Reading


def train() -> list[dict]:
    app = create_app()
    with app.app_context():
        rows = get_session().execute(
            select(
                Reading.home_id,
                Reading.room_id,
                Reading.sensor_id,
                Reading.metric_code,
                Reading.measured_at,
                Reading.value,
            )
            .where(Reading.source.in_(("device", "dataset")))
            .order_by(Reading.measured_at)
        )
        groups = defaultdict(list)
        for home_id, room_id, sensor_id, metric_code, measured_at, value in rows:
            key = (home_id, room_id, sensor_id, metric_code)
            groups[key].append((measured_at, float(value)))

        models = []
        for (home_id, room_id, sensor_id, metric_code), samples in groups.items():
            result = evaluate_and_fit(samples)
            models.append(
                {
                    "home_id": home_id,
                    "room_id": room_id,
                    "sensor_id": sensor_id,
                    "metric": metric_code,
                    **result,
                }
            )

        model_path = Path(app.instance_path) / "forecast_models.json"
        save_models(model_path, models)
        print(f"Evaluated {len(groups)} real-data series; saved {model_path}.")
        return models


if __name__ == "__main__":
    train()
