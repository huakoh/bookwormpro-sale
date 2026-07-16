"""
Cron subcommand for bookworm CLI.

Handles standalone cron management commands like list, create, edit,
pause/resume/run/remove, status, and tick.
"""

import json
import sys
from pathlib import Path
from typing import Iterable, List, Optional

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from bwm_cli.colors import Colors, color
from bwm_cli.i18n import _



def _normalize_skills(single_skill=None, skills: Optional[Iterable[str]] = None) -> Optional[List[str]]:
    if skills is None:
        if single_skill is None:
            return None
        raw_items = [single_skill]
    else:
        raw_items = list(skills)

    normalized: List[str] = []
    for item in raw_items:
        text = str(item or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _cron_api(**kwargs):
    from tools.cronjob_tools import cronjob as cronjob_tool

    return json.loads(cronjob_tool(**kwargs))


def cron_list(show_all: bool = False):
    """List all scheduled jobs."""
    from cron.jobs import list_jobs

    jobs = list_jobs(include_disabled=show_all)

    if not jobs:
        print(color(_("No scheduled jobs."), Colors.DIM))
        print(color(_("Create one with 'bookworm cron create ...' or the /cron command in chat."), Colors.DIM))
        return

    print()
    print(color("┌─────────────────────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color(_("│                         Scheduled Jobs                                  │"), Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────────────────────┘", Colors.CYAN))
    print()

    for job in jobs:
        job_id = job.get("id", "?")
        name = job.get("name", "(unnamed)")
        schedule = job.get("schedule_display", job.get("schedule", {}).get("value", "?"))
        state = job.get("state", "scheduled" if job.get("enabled", True) else "paused")
        next_run = job.get("next_run_at", "?")

        repeat_info = job.get("repeat", {})
        repeat_times = repeat_info.get("times")
        repeat_completed = repeat_info.get("completed", 0)
        repeat_str = f"{repeat_completed}/{repeat_times}" if repeat_times else "∞"

        deliver = job.get("deliver", ["local"])
        if isinstance(deliver, str):
            deliver = [deliver]
        deliver_str = ", ".join(deliver)

        skills = job.get("skills") or ([job["skill"]] if job.get("skill") else [])
        if state == "paused":
            status = color(_("[paused]"), Colors.YELLOW)
        elif state == "completed":
            status = color(_("[completed]"), Colors.BLUE)
        elif job.get("enabled", True):
            status = color(_("[active]"), Colors.GREEN)
        else:
            status = color(_("[disabled]"), Colors.RED)

        print(f"  {color(job_id, Colors.YELLOW)} {status}")
        print(_("    Name:      {name}").format(name=name))
        print(_("    Schedule:  {schedule}").format(schedule=schedule))
        print(_("    Repeat:    {repeat_str}").format(repeat_str=repeat_str))
        print(_("    Next run:  {next_run}").format(next_run=next_run))
        print(_("    Deliver:   {deliver_str}").format(deliver_str=deliver_str))
        if skills:
            print(_("    Skills:    {skills}").format(skills=', '.join(skills)))
        script = job.get("script")
        if script:
            print(_("    Script:    {script}").format(script=script))
        workdir = job.get("workdir")
        if workdir:
            print(_("    Workdir:   {workdir}").format(workdir=workdir))

        # Execution history
        last_status = job.get("last_status")
        if last_status:
            last_run = job.get("last_run_at", "?")
            if last_status == "ok":
                status_display = color("ok", Colors.GREEN)
            else:
                status_display = color(f"{last_status}: {job.get('last_error', '?')}", Colors.RED)
            print(_("    Last run:  {last_run}  {status_display}").format(last_run=last_run, status_display=status_display))

        delivery_err = job.get("last_delivery_error")
        if delivery_err:
            print(f"    {color(_('[警告] Delivery failed:'), Colors.YELLOW)} {delivery_err}")

        print()

    from bwm_cli.gateway import find_gateway_pids
    if not find_gateway_pids():
        print(color(_("  [警告]  Gateway is not running — jobs won't fire automatically."), Colors.YELLOW))
        print(color(_("     Start it with: bookworm gateway install"), Colors.DIM))
        print(color(_("                    sudo bookworm gateway install --system  # Linux servers"), Colors.DIM))
        print()


def cron_tick():
    """Run due jobs once and exit."""
    from cron.scheduler import tick
    tick(verbose=True)


def cron_status():
    """Show cron execution status."""
    from cron.jobs import list_jobs
    from bwm_cli.gateway import find_gateway_pids

    print()

    pids = find_gateway_pids()
    if pids:
        print(color(_("[成功] Gateway is running — cron jobs will fire automatically"), Colors.GREEN))
        print(_("  PID: {pids}").format(pids=', '.join(map(str, pids))))
    else:
        print(color(_("[失败] Gateway is not running — cron jobs will NOT fire"), Colors.RED))
        print()
        print(_("  To enable automatic execution:"))
        print(_("    bookworm gateway install    # Install as a user service"))
        print(_("    sudo bookworm gateway install --system  # Linux servers: boot-time system service"))
        print(_("    bookworm gateway            # Or run in foreground"))

    print()

    jobs = list_jobs(include_disabled=False)
    if jobs:
        next_runs = [j.get("next_run_at") for j in jobs if j.get("next_run_at")]
        print(_("  {len} active job(s)").format(len=len(jobs)))
        if next_runs:
            print(_("  Next run: {min}").format(min=min(next_runs)))
    else:
        print(_("  No active jobs"))

    print()


def cron_create(args):
    result = _cron_api(
        action="create",
        schedule=args.schedule,
        prompt=args.prompt,
        name=getattr(args, "name", None),
        deliver=getattr(args, "deliver", None),
        repeat=getattr(args, "repeat", None),
        skill=getattr(args, "skill", None),
        skills=_normalize_skills(getattr(args, "skill", None), getattr(args, "skills", None)),
        script=getattr(args, "script", None),
        workdir=getattr(args, "workdir", None),
    )
    if not result.get("success"):
        print(color(_("Failed to create job: {result}").format(result=result.get('error', 'unknown error')), Colors.RED))
        return 1
    print(color(_("Created job: {result}").format(result=result['job_id']), Colors.GREEN))
    print(_("  Name: {result}").format(result=result['name']))
    print(_("  Schedule: {result}").format(result=result['schedule']))
    if result.get("skills"):
        print(_("  Skills: {join_skills}").format(join_skills=', '.join(result['skills'])))
    job_data = result.get("job", {})
    if job_data.get("script"):
        print(_("  Script: {job_data}").format(job_data=job_data['script']))
    if job_data.get("workdir"):
        print(_("  Workdir: {job_data}").format(job_data=job_data['workdir']))
    print(_("  Next run: {result}").format(result=result['next_run_at']))
    return 0


def cron_edit(args):
    from cron.jobs import get_job

    job = get_job(args.job_id)
    if not job:
        print(color(_("Job not found: {args_job_id}").format(args_job_id=args.job_id), Colors.RED))
        return 1

    existing_skills = list(job.get("skills") or ([] if not job.get("skill") else [job.get("skill")]))
    replacement_skills = _normalize_skills(getattr(args, "skill", None), getattr(args, "skills", None))
    add_skills = _normalize_skills(None, getattr(args, "add_skills", None)) or []
    remove_skills = set(_normalize_skills(None, getattr(args, "remove_skills", None)) or [])

    final_skills = None
    if getattr(args, "clear_skills", False):
        final_skills = []
    elif replacement_skills is not None:
        final_skills = replacement_skills
    elif add_skills or remove_skills:
        final_skills = [skill for skill in existing_skills if skill not in remove_skills]
        for skill in add_skills:
            if skill not in final_skills:
                final_skills.append(skill)

    result = _cron_api(
        action="update",
        job_id=args.job_id,
        schedule=getattr(args, "schedule", None),
        prompt=getattr(args, "prompt", None),
        name=getattr(args, "name", None),
        deliver=getattr(args, "deliver", None),
        repeat=getattr(args, "repeat", None),
        skills=final_skills,
        script=getattr(args, "script", None),
        workdir=getattr(args, "workdir", None),
    )
    if not result.get("success"):
        print(color(_("Failed to update job: {result}").format(result=result.get('error', 'unknown error')), Colors.RED))
        return 1

    updated = result["job"]
    print(color(_("Updated job: {updated}").format(updated=updated['job_id']), Colors.GREEN))
    print(_("  Name: {updated}").format(updated=updated['name']))
    print(_("  Schedule: {updated}").format(updated=updated['schedule']))
    if updated.get("skills"):
        print(_("  Skills: {join_skills}").format(join_skills=', '.join(updated['skills'])))
    else:
        print(_("  Skills: none"))
    if updated.get("script"):
        print(_("  Script: {updated}").format(updated=updated['script']))
    if updated.get("workdir"):
        print(_("  Workdir: {updated}").format(updated=updated['workdir']))
    return 0


def _job_action(action: str, job_id: str, success_verb: str) -> int:
    result = _cron_api(action=action, job_id=job_id)
    if not result.get("success"):
        print(color(_("Failed to {action} job: {result}").format(action=action, result=result.get('error', 'unknown error')), Colors.RED))
        return 1
    job = result.get("job") or result.get("removed_job") or {}
    print(color(_("{success_verb} job: {job} ({job_id})").format(success_verb=success_verb, job=job.get('name', job_id), job_id=job_id), Colors.GREEN))
    if action in {"resume", "run"} and result.get("job", {}).get("next_run_at"):
        print(_("  Next run: {result}").format(result=result['job']['next_run_at']))
    if action == "run":
        print(_("  It will run on the next scheduler tick."))
    return 0


def cron_command(args):
    """Handle cron subcommands."""
    subcmd = getattr(args, 'cron_command', None)

    if subcmd is None or subcmd == "list":
        show_all = getattr(args, 'all', False)
        cron_list(show_all)
        return 0

    if subcmd == "status":
        cron_status()
        return 0

    if subcmd == "tick":
        cron_tick()
        return 0

    if subcmd in {"create", "add"}:
        return cron_create(args)

    if subcmd == "edit":
        return cron_edit(args)

    if subcmd == "pause":
        return _job_action("pause", args.job_id, "Paused")

    if subcmd == "resume":
        return _job_action("resume", args.job_id, "Resumed")

    if subcmd == "run":
        return _job_action("run", args.job_id, "Triggered")

    if subcmd in {"remove", "rm", "delete"}:
        return _job_action("remove", args.job_id, "Removed")

    print(_("Unknown cron command: {subcmd}").format(subcmd=subcmd))
    print(_("Usage: bookworm cron [list|create|edit|pause|resume|run|remove|status|tick]"))
    sys.exit(1)
