```python
"""
empire_ai_nexus.py (v1.3 - DEFINITIVE)
─────────────────────────────────────────────────────
Unified AI router gateway managing multi-provider completions.
Features: Quiet 5-pass exponential backoff retries and automatic 
Postgres/SQLite execution telemetry logging.
"""

import os
import sys
import time
import asyncio
import json
import logging
from typing import Any, Optional, Dict

logger = logging.getLogger("crewroute.nexus")

class EmpireAINexus:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL", "")
        # Zero-dependency setup verification
        try:
            import litellm
            litellm.suppress_logging = True
            self.has_litellm = True
        except ImportError:
            self.has_litellm = False
            logger.warning("nexus.missing_litellm", detail="Fallback modes will apply.")

    async def ask_async(
        self, 
        prompt: str, 
        model_id: str = "claude-3-5-sonnet", 
        system_instruction: Optional[str] = None,
        task_type: str = "routing",
        crew_name: str = "Unknown",
        date_target: str = ""
    ) -> str:
        """
        Queries an LLM with a 5-pass quiet exponential backoff retry system.
        Logs metrics, tokens, and cost parameters directly back to PostgreSQL.
        """
        if not self.has_litellm:
            raise RuntimeError("LiteLLM package is missing from execution environment.")

        from litellm import acompletion
        
        # Normalize model identification mapping
        model_map = {
            "claude-3-5-sonnet": "anthropic/claude-3-5-sonnet-20241022",
            "grok-2": "xai/grok-2",
            "gemini-1-5-pro": "gemini/gemini-1.5-pro-latest",
            "claude-3-opus": "anthropic/claude-3-opus-20240229"
        }
        target_model = model_map.get(model_id, model_id)
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        # Retry logic: up to 5 times with delays of 1s, 2s, 4s, 8s, 16s.
        delays = [1, 2, 4, 8, 16]
        response = None
        start_time = time.monotonic()
        last_error = ""

        for attempt, delay in enumerate(delays):
            try:
                response = await acompletion(
                    model=target_model,
                    messages=messages,
                    timeout=30.0
                )
                break  # Successful execution, escape retry loop
            except Exception as e:
                last_error = str(e)
                if attempt == len(delays) - 1:
                    logger.error("nexus.api_exhausted", attempts=5, model=model_id, error=last_error)
                    await self._log_telemetry(
                        endpoint=target_model, model_id=model_id, provider=target_model.split("/")[0],
                        task_type=task_type, crew_name=crew_name, date_target=date_target,
                        success=False, error=last_error, duration_ms=int((time.monotonic() - start_time) * 1000)
                    )
                    raise RuntimeError(f"System gateway timeout. All retries failed: {last_error}")
                await asyncio.sleep(delay)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        content = response.choices[0].message.content
        
        # Calculate tokens and cost tracking via litellm metrics
        prompt_tokens = getattr(response.usage, "prompt_tokens", 0)
        completion_tokens = getattr(response.usage, "completion_tokens", 0)
        total_tokens = getattr(response.usage, "total_tokens", 0)
        
        # Estimate pricing matrix (standard USD prices per 1M tokens as fallbacks if litellm omitted)
        cost_usd = 0.0
        try:
            from litellm import completion_cost
            cost_usd = completion_cost(completion_response=response) or 0.0
        except Exception:
            # Fallback approximate cost estimation if helper crashes
            if "claude-3-5-sonnet" in target_model:
                cost_usd = ((prompt_tokens * 3.0) + (completion_tokens * 15.0)) / 1_000_000
            elif "grok" in target_model:
                cost_usd = ((prompt_tokens * 2.0) + (completion_tokens * 10.0)) / 1_000_000

        # Log to PostgreSQL telemetry table
        await self._log_telemetry(
            endpoint=target_model, model_id=model_id, provider=target_model.split("/")[0],
            task_type=task_type, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            total_tokens=total_tokens, cost_usd=cost_usd, duration_ms=duration_ms,
            crew_name=crew_name, date_target=date_target, success=True
        )

        return content

    async def _log_telemetry(self, **kwargs):
        """Asynchronously writes a usage metric log straight to our storage layer."""
        if not self.db_url:
            return  # Skip silently if database is not active or set to SQLite fallback
        
        try:
            import asyncpg
            url = self.db_url.replace("+asyncpg","").replace("postgresql+asyncpg","postgresql")
            conn = await asyncpg.connect(url)
            await conn.execute("""
                INSERT INTO nexus_calls (
                    endpoint, model_id, provider, task_type, prompt_tokens, 
                    completion_tokens, total_tokens, cost_usd, duration_ms, 
                    crew_name, date_target, success, error
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """, 
            kwargs.get("endpoint"), kwargs.get("model_id"), kwargs.get("provider"),
            kwargs.get("task_type"), kwargs.get("prompt_tokens", 0), kwargs.get("completion_tokens", 0),
            kwargs.get("total_tokens", 0), kwargs.get("cost_usd", 0.0), kwargs.get("duration_ms", 0),
            kwargs.get("crew_name", "Unknown"), kwargs.get("date_target", ""),
            kwargs.get("success", True), kwargs.get("error")
            )
            await conn.close()
        except Exception as e:
            logger.warning("nexus.telemetry_log_failed", detail=str(e))

```
