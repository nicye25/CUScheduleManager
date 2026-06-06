from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from app.routes.schedules import schedules_bp


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    @app.get("/")
    def root() -> tuple[dict[str, object], int]:
        return {
            "status": "ok",
            "service": "SchedulePlanner API",
            "endpoints": {
                "health": "/health",
                "api_health": "/api/health",
                "schedule_combinations": "/api/schedules/combinations",
                "schedule_visualizer": "/api/schedules/visualizer",
            },
        }, 200

    @app.get("/health")
    def health() -> tuple[dict[str, str], int]:
        return {"status": "ok"}, 200

    @app.get("/favicon.ico")
    def favicon() -> tuple[str, int]:
        return "", 204

    app.register_blueprint(schedules_bp)
    return app
