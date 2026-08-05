"""Development AI bypass service.

This file intentionally does not import TensorFlow.
It creates deterministic demo anomaly scores from preprocessed data.
Use this only on development PC.
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple


logger = logging.getLogger("app")


class AIProcessingService:
    """AI inference bypass service for development PC."""

    def __init__(self):
        logger.info("AIProcessingService initialized in DEV BYPASS mode")

    async def run(self, data: List[dict]) -> List[dict]:
        input_count = len(data or [])

        if input_count == 0:
            logger.warning("DEV BYPASS AI skipped: empty input")
            return []

        logger.warning(
            "DEV BYPASS AI enabled - TensorFlow inference is skipped. "
            f"input_count={input_count}"
        )

        return self._make_demo_scores(data)

    async def process(self, data: List[dict]) -> List[dict]:
        return await self.run(data)

    def _make_demo_scores(self, data: List[dict]) -> List[dict]:
        groups: Dict[Tuple, dict] = {}

        for row in data:
            site_no = row.get("site_no", 0)
            bms_id = row.get("bms_id", "")
            bank_no = row.get("bank_no", row.get("bank_number", 1))
            rack_no = row.get("rack_no", row.get("rack_number", 0))
            string_no = row.get("string_no", row.get("string_number", 0))
            module_no = row.get("module_no", row.get("module_number", 0))

            key = (site_no, bms_id, bank_no, rack_no, string_no, module_no)

            if key not in groups:
                groups[key] = row

        results: List[dict] = []
        prediction_time = datetime.now()

        for idx, (key, sample) in enumerate(sorted(groups.items(), key=lambda x: x[0])):
            site_no, bms_id, bank_no, rack_no, string_no, module_no = key

            # Deterministic demo score. No random, no TensorFlow.
            base_score = 18.0 + ((idx * 7) % 55)

            cell_scores = {}
            cell_levels = {}

            max_score = 0.0
            total_score = 0.0
            max_level = "normal"

            for cell_no in range(1, 21):
                score = min(99.0, base_score + (cell_no % 5) * 2.5)
                level = self._score_to_level(score)

                cell_scores[f"cell_{cell_no}_score"] = round(score, 3)
                cell_levels[f"cell_{cell_no}_level"] = level

                max_score = max(max_score, score)
                total_score += score

                if self._level_rank(level) > self._level_rank(max_level):
                    max_level = level

            row = {
                "serial_number": (
                    sample.get("serial_number")
                    or sample.get("serial_no")
                    or sample.get("bms_id")
                    or bms_id
                ),
                "sensing_datetime": (
                    sample.get("sensing_datetime")
                    or sample.get("measured_at")
                    or sample.get("date_time")
                    or prediction_time
                ),
                "prediction_time": prediction_time,
                "bank_no": bank_no,
                "rack_no": rack_no,
                "string_no": string_no,
                "module_no": module_no,
                "max_score": round(max_score, 3),
                "max_level": max_level,
                "average_score": round(total_score / 20.0, 3),
                "maker": "dev-bypass",
            }

            row.update(cell_scores)
            row.update(cell_levels)

            results.append(row)

        logger.warning(f"DEV BYPASS AI completed: output_count={len(results)}")
        return results

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score >= 80:
            return "danger"
        if score >= 60:
            return "warning"
        return "normal"

    @staticmethod
    def _level_rank(level: str) -> int:
        ranks = {
            "normal": 0,
            "warning": 1,
            "danger": 2,
        }
        return ranks.get(str(level).lower(), 0)


AIService = AIProcessingService