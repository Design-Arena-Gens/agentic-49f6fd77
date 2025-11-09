from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Literal

import google.generativeai as genai
from loguru import logger
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

Decision = Literal["BUY", "SELL", "FLAT"]


class GeminiSignal(BaseModel):
  decision: Decision
  confidence: float = Field(ge=0, le=1)
  stop_loss_pips: float = Field(gt=0)
  take_profit_pips: float = Field(gt=0)
  rationale: str


@dataclass
class GeminiAdvisor:
  api_key: str
  model: str
  prompt_template: str

  def __post_init__(self) -> None:
    genai.configure(api_key=self.api_key)
    self._model = genai.GenerativeModel(self.model)

  @retry(wait=wait_exponential(multiplier=1, min=2, max=20), stop=stop_after_attempt(4))
  def analyse(
    self,
    symbol: str,
    timeframe: str,
    ohlcv_snapshot: Dict[str, Any],
    sentiment_notes: str,
    technical_summary: str,
  ) -> GeminiSignal:
    """Request trading signal from Gemini using structured prompt."""
    prompt = self.prompt_template.format(
      symbol=symbol,
      timeframe=timeframe,
      ohlcv=json.dumps(ohlcv_snapshot, ensure_ascii=False),
      sentiment=sentiment_notes,
      technical=technical_summary,
    )

    logger.debug("Submitting Gemini prompt for {}/{}.", symbol, timeframe)
    response = self._model.generate_content(
      prompt, generation_config={"temperature": 0.2, "response_mime_type": "application/json"}
    )

    text = response.text if hasattr(response, "text") else None
    if not text:
      logger.error("Gemini returned empty payload: {}", response)
      raise ValueError("Gemini returned empty payload.")

    logger.debug("Gemini raw response: {}", text)
    try:
      payload = json.loads(text)
    except json.JSONDecodeError as exc:
      logger.error("Failed to decode Gemini JSON: {}", exc)
      raise

    try:
      signal = GeminiSignal.model_validate(payload)
    except ValidationError as exc:
      logger.error("Invalid Gemini response: {}", exc)
      raise

    return signal
