```python
from __future__ import annotations
import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any, Optional
import urllib.request
import urllib.error
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ]
)
log = structlog.get_logger("crewroute.engine")

SPREADSHEET_ID = os.getenv("CJS_SHEET_ID", "")
HUB_PATH       = os.getenv("HUB_DB_PATH", "cjs_operating_hub.db")
JOBS_TAB       = "Jobs"
RESULTS_TAB    = "Route Plans"
LOG_TAB        = "Run Log"

JOBS_HEADER = ["date","job_id","client","address","city","crew","window","type","value","urgency","duration_mins","notes"]
RESULTS_HEADER = ["run_date","date","crew","order","job_id","client","window","type","value","assignment_reason","drive_note"]
LOG_HEADER = ["run_at","date","crew","jobs_loaded","dlq_count","time_saved_mins","total_value","status","error","debate_used","model_used"]

MAX_SHEET_RETRIES = 3
SHEET_RETRY_DELAY = 2.0

@dataclass
class Job:
    id: str; client: str; address: str; city: str; crew: str; window: str; job_type: str; value: int
    urgency: str = "track"; duration_mins: int = 90; notes: str = ""; date: str = ""
    def to_dict(self): return asdict(self)
    def display(self):
        tag = {"late":"🔴","risk":"🟡","track":"🟢","done":"✅"}.get(self.urgency,"•")
        return f"{tag} J-{self.id} | {self.client} | ${self.value}"

@dataclass
class RoutePlan:
    date: str; crew: str; ordered_jobs: list[dict]; time_saved_mins: int = 0; total_value: int = 0
    summary: str = ""; method: str = "rule_based"; debate_used: bool = False
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

@dataclass
class RunResult:
    success: bool; plan: Optional[RoutePlan] = None; jobs_loaded: int = 0; dlq_count: int = 0
    error: str = ""; duration_secs: float = 0.0; debate_used: bool = False; model_used: str = ""; governor: dict = field(default_factory=dict)

class SheetsClient:
    def __init__(self):
        self._gc = None; self._sheet = None; self._tabs = {}
    def connect(self):
        import gspread
        creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
        if creds_json:
            self._gc = gspread.service_account_from_dict(json.loads(creds_json))
        elif os.path.exists("credentials.json"):
            self._gc = gspread.service_account(filename="credentials.json")
        else:
            self._gc = gspread.oauth()
        if not SPREADSHEET_ID: raise ValueError("CJS_SHEET_ID not set.")
        self._sheet = self._gc.open_by_key(SPREADSHEET_ID)
    def _ensure(self):
        if not self._gc: self.connect()
    def _tab(self, name: str):
        self._ensure()
        if name not in self._tabs: self._tabs[name] = self._sheet.worksheet(name)
        return self._tabs[name]
    def _retry(self, fn, *args, **kwargs):
        for attempt in range(1, MAX_SHEET_RETRIES + 1):
            try: return fn(*args, **kwargs)
            except Exception as e:
                if attempt == MAX_SHEET_RETRIES: raise e
                time.sleep(SHEET_RETRY_DELAY * attempt)
    def setup_tabs(self):
        self._ensure()
        existing = {ws.title for ws in self._sheet.worksheets()}
        specs = [(JOBS_TAB, JOBS_HEADER, 500, 12), (RESULTS_TAB, RESULTS_HEADER, 500, 11), (LOG_TAB, LOG_HEADER, 200, 11)]
        for name, header, rows, cols in specs:
            if name not in existing:
                ws = self._sheet.add_worksheet(title=name, rows=rows, cols=cols)
                ws.append_row(header)
                ws.freeze(rows=1)
                self._tabs[name] = ws
    def read_jobs(self, target_date: Optional[str] = None, crew_filter: Optional[str] = None) -> tuple[list[Job], list[dict]]:
        self._ensure()
        target = _normalize_date(target_date or date.today().isoformat())
        rows = self._retry(self._tab(JOBS_TAB).get_all_records, default_blank="")
        jobs, dlq = [], []
        for i, row in enumerate(rows, start=2):
            if _normalize_date(str(row.get("date",""))) != target: continue
            crew = str(row.get("crew","")).strip()
            if crew_filter and crew.lower() != crew_filter.lower(): continue
            client = str(row.get("client","")).strip()
            if not client:
                dlq.append({"row":i,"reason":"missing client","row_data":dict(row)})
                continue
            try:
                val = int(float(str(row.get("value", 0) or 0)))
                dur = int(float(str(row.get("duration_mins", 90) or 90)))
            except Exception as e:
                dlq.append({"row":i,"reason":f"bad value: {e}","row_data":dict(row)})
                continue
            jobs.append(Job(
                id=str(row.get("job_id","")).strip() or f"AUTO-{i:04d}", client=client,
                address=str(row.get("address","")).strip(), city=str(row.get("city","")).strip(),
                crew=crew, window=str(row.get("window","")).strip(), job_type=str(row.get("type","Maintenance")).strip(),
                value=val, urgency=str(row.get("urgency","track")).strip().lower(), duration_mins=dur,
                notes=str(row.get("notes","")).strip(), date=target
            ))
        jobs.sort(key=lambda j: {"late":0,"risk":1,"track":2,"done":3}.get(j.urgency, 2))
        return jobs, dlq
    def write_route_plan(self, plan: RoutePlan):
        self._ensure()
        ws = self._tab(RESULTS_TAB)
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        rows = []
        for idx, job in enumerate(plan.ordered_jobs, 1):
            rows.append([now, plan.date, plan.crew, idx, job.get("id",""), job.get("client",""), job.get("window",""), job.get("job_type",""), job.get("value",""), job.get("assignment_reason",""), job.get("drive_note","")])
        self._retry(ws.append_rows, rows)
    def write_run_log(self, result: RunResult, crew: str, target_date: str):
        self._ensure()
        p = result.plan
        self._retry(self._tab(LOG_TAB).append_row, [
            datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"), target_date, crew, result.jobs_loaded, result.dlq_count,
            p.time_saved_mins if p else 0, p.total_value if p else 0, "✅ success" if result.success else "❌ failed",
            result.error[:200] if result.error else "", "yes" if result.debate_used else "no", result.model_used or ""
        ])
    @property
    def sheet_url(self) -> str: return f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"


def _shape_for_make(plan_dict: dict) -> dict:
    """Filter payload keys to enforce the airtable_payload_map.json contract strictly."""
    AIRTABLE_JOB_KEYS = {"id", "client", "crew", "window", "job_type", "value", "assignment_reason", "drive_note"}
    return {
        "date":        plan_dict.get("date"),
        "crew":        plan_dict.get("crew"),
        "total_value": plan_dict.get("total_value"),
        "ordered_jobs": [
            {k: v for k, v in job.items() if k in AIRTABLE_JOB_KEYS}
            for job in plan_dict.get("ordered_jobs", [])
        ],
    }


# ── Claude's Webhook Dispatcher (Zero-Dependency) ─────────────
async def dispatch_to_make(route_plan_dict: dict, timeout_secs: int = 15) -> bool:
    webhook_url = os.getenv("MAKE_WEBHOOK_URL", "").strip()
    if not webhook_url:
        log.info("webhook.skipped", reason="MAKE_WEBHOOK_URL not set")
        return False
    if not webhook_url.startswith("https://"):
        log.warning("webhook.invalid_url", reason="MAKE_WEBHOOK_URL must begin with https://")
        return False

    payload = {
        "source": "crewroute_os",
        "schema_version": "1.0",
        "dispatched_at": datetime.utcnow().isoformat() + "Z",
        "route_plan": route_plan_dict,
    }

    def _blocking_post() -> tuple[int, str]:
        body = json.dumps(payload, default=str).encode("utf-8")
        req  = urllib.request.Request(
            url=webhook_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "CrewRoute-OS/1.0",
                "X-Source": "crewroute_daily_engine",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout_secs) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")

    try:
        loop = asyncio.get_running_loop()
        status, body = await asyncio.wait_for(
            loop.run_in_executor(None, _blocking_post),
            timeout=timeout_secs + 2,
        )
        if 200 <= status < 300:
            log.info("webhook.sent", status=status, crew=route_plan_dict.get("crew", "?"), jobs=len(route_plan_dict.get("ordered_jobs", [])))
            return True
        log.warning("webhook.rejected", status=status, body=body[:200])
        return False
    except asyncio.TimeoutError:
        log.warning("webhook.timeout", cap_secs=timeout_secs, webhook_url=webhook_url[:60] + "...")
        return False
    except urllib.error.HTTPError as e:
        log.warning("webhook.http_error", code=e.code, reason=str(e.reason)[:120])
        return False
    except urllib.error.URLError as e:
        log.warning("webhook.url_error", reason=str(e.reason)[:120])
        return False
    except Exception as e:
        log.error("webhook.unexpected", error=type(e).__name__, detail=str(e)[:200])
        return False


def _write_dlq_rows(dlq: list[dict]):
    if not dlq or not os.path.exists(HUB_PATH): return
    try:
        import sqlite3
        conn = sqlite3.connect(HUB_PATH, timeout=10)
        conn.execute("CREATE TABLE IF NOT EXISTS dead_letter_queue (id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))), agent_name TEXT, task_id TEXT, input_json TEXT, error TEXT, retry_count INTEGER DEFAULT 0, resolved INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now')))")
        for row in dlq:
            conn.execute("INSERT INTO dead_letter_queue (agent_name, task_id, input_json, error) VALUES (?,?,?,?)", ("SheetsReader", f"row-{row.get('row','?')}", json.dumps(row.get('row_data',{}), default=str), row.get('reason','unknown')))
        conn.commit(); conn.close()
    except Exception as e: log.error("dlq.write_failed", error=str(e))

async def run_pipeline(target_date: Optional[str] = None, crew_filter: Optional[str] = None, sheets: Optional[SheetsClient] = None, dry_run: bool = False) -> RunResult:
    t0 = time.monotonic()
    target_date = _normalize_date(target_date or date.today().isoformat())
    sc = sheets or SheetsClient()
    try: jobs, dlq = sc.read_jobs(target_date, crew_filter or None)
    except Exception as e: return RunResult(success=False, error=f"Sheets read failed: {e}", duration_secs=time.monotonic()-t0)
    if dlq: _write_dlq_rows(dlq)
    if not jobs: return RunResult(success=False, error="No jobs found", duration_secs=time.monotonic()-t0)
    
    optimizer = OptimizerAgent(hub_path=HUB_PATH)
    opt_result = await optimizer.run(jobs=[j.to_dict() for j in jobs], crew=crew_filter or jobs[0].crew, target_date=target_date)
    if not opt_result.success: return RunResult(success=False, error=opt_result.error, duration_secs=time.monotonic()-t0)
    
    plan = RoutePlan(
        date=target_date, crew=crew_filter or jobs[0].crew, ordered_jobs=opt_result.data.get("ordered_jobs", []),
        time_saved_mins=opt_result.data.get("time_saved_mins", 0), total_value=opt_result.data.get("total_value", 0),
        summary="Optimized Route Plan", method=opt_result.model_used, debate_used=opt_result.data.get("debate_used", False)
    )
    if not dry_run:
        try: sc.write_route_plan(plan)
        except Exception as e: log.error("sheets.write_failed", error=str(e))
    
    # ── Dispatch to Make.com Webhook (Leak 4 Resolved) ────────
    if not dry_run:
        import dataclasses
        plan_dict = dataclasses.asdict(plan)
        shaped_payload = _shape_for_make(plan_dict)
        webhook_ok = await dispatch_to_make(shaped_payload)
        if not webhook_ok:
            log.warning("pipeline.webhook_not_delivered")
            
    governor_data = {}
    try:
        governor = GovernorAgent(hub_path=HUB_PATH)
        gov_result = await governor.evaluate(target_date=target_date, crew=crew_filter or None)
        governor_data = gov_result.data
    except Exception as e: log.warning("governor.failed", error=str(e))
    
    res = RunResult(success=True, plan=plan, jobs_loaded=len(jobs), dlq_count=len(dlq), debate_used=plan.debate_used, model_used=opt_result.model_used, governor=governor_data, duration_secs=time.monotonic()-t0)
    if not dry_run:
        try: sc.write_run_log(res, crew_filter or "all", target_date)
        except Exception as e: log.warning("log.failed", error=str(e))

    # ── Mobile Dispatch Alerts Wiring (Leak 3 Resolved) ───────
    if not dry_run:
        try:
            from alerts import dispatch_alert
            verdict_status = governor_data.get("status", "unknown")
            if verdict_status in ("yellow", "red") or res.success:
                await dispatch_alert(
                    title=f"CrewRoute {target_date} — {verdict_status.upper()}",
                    body=res.plan.summary if res.plan and res.plan.summary else f"Jobs loaded: {res.jobs_loaded}. Value: ${res.plan.total_value if res.plan else 0}",
                    status=verdict_status,
                )
        except ImportError:
            log.warning("alerts.import_failed", detail="alerts.py missing or failed to import dispatch_alert")
        except Exception as e:
            log.warning("alerts.send_failed", error=str(e))

    return res

def _get_agents():
    import importlib
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    mod = importlib.import_module("crewroute_agents")
    return mod.OptimizerAgent, mod.GovernorAgent

def OptimizerAgent(**kwargs): return _get_agents()[0](**kwargs)
def GovernorAgent(**kwargs): return _get_agents()[1](**kwargs)

def start_scheduler(run_time: str = "06:00", crew_filter: Optional[str] = None) -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.executors.pool import ThreadPoolExecutor
    from apscheduler.triggers.cron import CronTrigger
    hour, minute = run_time.split(":")
    sc = SheetsClient()
    scheduler = BlockingScheduler(
        jobstores={"default": SQLAlchemyJobStore(url=os.getenv("SCHEDULER_DB", "sqlite:///crewroute_scheduler.db"))},
        executors={"default": ThreadPoolExecutor(max_workers=2)},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600},
        timezone="America/Los_Angeles"
    )
    scheduler.add_job(lambda: asyncio.run(run_pipeline(target_date=date.today().isoformat(), crew_filter=crew_filter, sheets=sc)), trigger=CronTrigger(hour=int(hour), minute=int(minute)), id="crewroute_daily", replace_existing=True)
    scheduler.start()

def _normalize_date(d: str) -> str:
    d = d.strip()
    if len(d)==10 and d[4]=="-": return d
    return d

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--schedule", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--date", default=None)
    parser.add_argument("--crew", default=None)
    parser.add_argument("--time", default="06:00")
    args = parser.parse_args()
    sc = SheetsClient()
    if args.setup: sc.setup_tabs(); print("Tabs ready."); return
    if args.schedule: start_scheduler(run_time=args.time, crew_filter=args.crew); return
    result = await run_pipeline(target_date=args.date, crew_filter=args.crew, sheets=sc, dry_run=args.dry_run)
    print(f"Run complete. Success: {result.success}")

if __name__ == "__main__": asyncio.run(main())

```
