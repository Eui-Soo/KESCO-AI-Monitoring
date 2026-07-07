"""AI 처리 서비스.

schedule_service.py에서 넘겨준 rolling 7일 전처리 데이터를
ai/ai_process.py의 ai_process() 함수로 전달한다.

실제 STGCN 모델 로딩은 서버 시작 시점이 아니라,
AI 실행 시점에 ai_process.py 내부에서 수행된다.
"""

import asyncio
import logging
from typing import List


logger = logging.getLogger("app")


class AIProcessingService:
    """AI 추론 서비스."""

    def __init__(self):
        logger.info("✅ AIProcessingService 초기화 완료")

    async def run(self, data: List[dict]) -> List[dict]:
        """AI 추론을 비동기로 실행한다."""

        input_count = len(data or [])

        if input_count == 0:
            logger.warning("AI 처리 생략: 입력 데이터가 없습니다.")
            return []

        logger.info(f"▶ AI 처리 시작: input_count={input_count}")

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            self._run_ai_process,
            data,
        )

        if results is None:
            results = []

        logger.info(f"✅ AI 처리 완료: output_count={len(results)}")
        return results

    async def process(self, data: List[dict]) -> List[dict]:
        """기존 코드 호환용 함수."""
        return await self.run(data)

    @staticmethod
    def _run_ai_process(data: List[dict]) -> List[dict]:
        """실제 ai_process.py의 ai_process()를 호출한다.

        여기서 import하는 이유:
        - 서버 시작 시 TensorFlow를 바로 로딩하지 않기 위해서
        - 실제 AI 실행 시점에만 모델 관련 코드를 불러오기 위해서
        """
        from ai.ai_process import ai_process

        return ai_process(data)


# 기존 코드 호환용 별칭
AIService = AIProcessingService