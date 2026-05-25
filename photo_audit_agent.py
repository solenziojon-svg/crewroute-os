async def process_job_completion(
    job_id:       str,
    transcript:   str         = "",
    photo_url:    Optional[str] = None,
    photo_base64: Optional[str] = None,
    client_name:  str         = "",
    job_type:     str         = "Maintenance",
    crew:         str         = "Solo",
    date:         Optional[str] = None,
    hub_path:     str         = "cjs_operating_hub.db",
    dry_run:      bool        = False,
) -> dict:
    """
    Unified entry point for Voice + Photo processing.
    Now includes Safe Mode awareness from GovernorAgent.
    """
    from solo_pilot_agent import SoloPilotAgent

    t0   = time.monotonic()
    date = date or datetime.utcnow().strftime("%Y-%m-%d")

    bind_context(job_id=job_id, client_name=client_name, dry_run=dry_run)

    if not job_id or not str(job_id).strip():
        return {"success": False, "error": "job_id is required"}

    has_voice = bool(transcript and transcript.strip())
    has_photo = bool(photo_url or photo_base64)

    if not has_voice and not has_photo:
        return {"success": False, "error": "Nothing to process"}

    # ── Safe Mode Check ─────────────────────────────────────
    safe_mode_active = False
    safe_mode_reason = ""

    try:
        from cjs_operating_hub import EmpireHub
        with EmpireHub(hub_path) as hub:
            safe_mode_active, safe_mode_reason = hub.is_safe_mode_active(date)
    except Exception as e:
        logger.warning("safe_mode_check_failed", error=str(e))

    if safe_mode_active:
        logger.warning("safe_mode_active", date=date, reason=safe_mode_reason)
        # In Safe Mode we skip vision to save cost and respect governance
        has_photo = False
        # We can still process voice/text lightly

    logger.info(
        "process_job_completion_started",
        has_voice=has_voice,
        has_photo=has_photo,
        safe_mode=safe_mode_active,
    )

    # ── Run agents with isolation ───────────────────────────
    async def _run_voice():
        try:
            agent = SoloPilotAgent(hub_path=hub_path)
            result = await agent.process_voice_note(
                transcript=transcript, job_id=job_id, crew=crew,
                client_name=client_name, job_type=job_type, date=date, dry_run=dry_run,
            )
            return result.to_dict()
        except Exception as e:
            logger.error("voice_agent_failed", error=str(e))
            return None

    async def _run_photo():
        if not has_photo:
            return None
        try:
            agent = PhotoAuditAgent(hub_path=hub_path)
            result = await agent.analyze(
                job_id=job_id, photo_url=photo_url, photo_base64=photo_base64,
                client_name=client_name, job_type=job_type, date=date, dry_run=dry_run,
            )
            return result.to_dict()
        except Exception as e:
            logger.error("photo_agent_failed", error=str(e))
            return None

    coros = []
    if has_voice:
        coros.append(_run_voice())
    if has_photo:
        coros.append(_run_photo())

    results = await asyncio.gather(*coros, return_exceptions=True)

    voice_data = results[0] if has_voice and not isinstance(results[0], Exception) else None
    photo_data = results[-1] if has_photo and not isinstance(results[-1], Exception) else None

    any_success = (voice_data is not None) or (photo_data is not None)
    if not any_success:
        return {"success": False, "error": "All agents failed", "safe_mode": safe_mode_active}

    # ── Merge results ───────────────────────────────────────
    client_message = ""
    if voice_data and voice_data.get("client_message"):
        client_message = voice_data["client_message"]
    if photo_data and photo_data.get("client_caption") and photo_data.get("quality_status") == "verified":
        client_message = f"{client_message}\n\n📸 {photo_data['client_caption']}".strip()

    upsell_prompt = ""
    if photo_data and photo_data.get("upsell_detected"):
        upsell_prompt = photo_data.get("upsell_text", "")
    elif voice_data:
        upsell_prompt = voice_data.get("upsell_prompt", "")

    flags = []
    if photo_data and photo_data.get("gate_flag"):
        flags.append(f"gate: {photo_data.get('gate_note', '')}")

    duration_ms = int((time.monotonic() - t0) * 1000)

    return {
        "success": True,
        "job_id": job_id,
        "dry_run": dry_run,
        "safe_mode_active": safe_mode_active,
        "safe_mode_reason": safe_mode_reason,
        "voice": voice_data,
        "photo": photo_data,
        "client_message": client_message,
        "upsell_prompt": upsell_prompt,
        "flags": flags,
        "duration_ms": duration_ms,
    }