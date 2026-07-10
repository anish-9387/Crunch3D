import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ..api.schemas import FeedbackRequest

TRAINING_DIR = Path(__file__).parent.parent / "training"
OPTIMIZATION_EVENTS_FILE = TRAINING_DIR / "optimization_events.jsonl"
FEEDBACK_EVENTS_FILE = TRAINING_DIR / "feedback_events.jsonl"
PREFERENCE_MODEL_FILE = TRAINING_DIR / "preference_model.json"

TRAINING_DIR.mkdir(exist_ok=True)


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []

    records: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_optimization_event(
    *,
    job_id: str,
    original_stats: dict,
    optimized_stats: dict,
    request_payload: dict,
    quality_meta: dict,
    processing_time_seconds: float,
    reduction_percent: float,
) -> None:
    event = {
        "timestamp_utc": _utc_now(),
        "job_id": job_id,
        "request": request_payload,
        "original_stats": original_stats,
        "optimized_stats": optimized_stats,
        "quality_meta": quality_meta,
        "processing_time_seconds": processing_time_seconds,
        "reduction_percent": reduction_percent,
    }
    _append_jsonl(OPTIMIZATION_EVENTS_FILE, event)


def _feedback_recommendations(feedback: FeedbackRequest) -> list[str]:
    if feedback.satisfied:
        return [
            "Current optimization profile met user expectation. Keep this sample as a high-quality baseline.",
            "Prioritize similar request patterns when ranking presets for future users.",
        ]

    recs: list[str] = [
        "Decrease reduction aggressiveness for this request type (increase target face count).",
        "Increase strict quality protections and tighten allowed surface deviation.",
    ]

    if not feedback.preserve_shape:
        recs.append("Increase boundary and silhouette protection to better preserve overall shape.")
    if not feedback.preserve_vertices:
        recs.append("Apply softer vertex-collapse scheduling to retain key vertex structure.")
    if not feedback.preserve_faces:
        recs.append("Bias optimizer toward face-distribution stability instead of uniform collapse.")

    issue_text = " ".join(feedback.issues or []).lower()
    notes_text = (feedback.notes or "").lower()
    combined = f"{issue_text} {notes_text}"

    if "texture" in combined or "uv" in combined:
        recs.append("Add UV-preservation constraints and post-decimation UV validation.")
    if "normal" in combined or "shading" in combined:
        recs.append("Recompute normals with stronger smoothing controls after decimation.")
    if "hole" in combined or "crack" in combined:
        recs.append("Run topology repair pass to fix non-manifold edges and tiny holes.")

    return recs


def record_feedback_event(
    *,
    feedback: FeedbackRequest,
    optimization_snapshot: dict | None,
) -> list[str]:
    recommendations = _feedback_recommendations(feedback)
    event = {
        "timestamp_utc": _utc_now(),
        "job_id": feedback.job_id,
        "feedback": feedback.model_dump(),
        "recommendations": recommendations,
        "optimization_snapshot": optimization_snapshot,
    }
    _append_jsonl(FEEDBACK_EVENTS_FILE, event)
    return recommendations


def get_training_summary() -> dict:
    optimization_events = _read_jsonl(OPTIMIZATION_EVENTS_FILE)
    feedback_events = _read_jsonl(FEEDBACK_EVENTS_FILE)

    positive_feedback = 0
    negative_feedback = 0
    issue_counter: Counter[str] = Counter()

    for item in feedback_events:
        feedback = item.get("feedback", {})
        if feedback.get("satisfied"):
            positive_feedback += 1
        else:
            negative_feedback += 1
            for issue in feedback.get("issues", []) or []:
                cleaned = str(issue).strip()
                if cleaned:
                    issue_counter[cleaned] += 1

    suggested_focus_areas: list[str] = []
    if negative_feedback > 0:
        suggested_focus_areas.append("Improve quality guard adaptation for aggressive reductions.")
    if issue_counter:
        suggested_focus_areas.append("Tune optimizer around repeated user-reported issue categories.")
    if not suggested_focus_areas:
        suggested_focus_areas.append("Collect more feedback samples to bootstrap training confidence.")

    return {
        "total_optimization_events": len(optimization_events),
        "total_feedback_events": len(feedback_events),
        "positive_feedback": positive_feedback,
        "negative_feedback": negative_feedback,
        "top_negative_issues": [name for name, _ in issue_counter.most_common(5)],
        "suggested_focus_areas": suggested_focus_areas,
    }


def bootstrap_preference_model() -> dict:
    optimization_events = _read_jsonl(OPTIMIZATION_EVENTS_FILE)
    feedback_events = _read_jsonl(FEEDBACK_EVENTS_FILE)

    feedback_by_job: dict[str, dict] = {}
    for event in feedback_events:
        feedback = event.get("feedback", {})
        job_id = event.get("job_id")
        if not job_id:
            continue
        feedback_by_job[str(job_id)] = feedback

    grouped: dict[str, dict] = {}
    used_samples = 0

    for event in optimization_events:
        job_id = str(event.get("job_id", ""))
        if not job_id:
            continue

        feedback = feedback_by_job.get(job_id)
        if not feedback or not feedback.get("satisfied"):
            continue

        request = event.get("request", {})
        desired_output = request.get("desired_output") or {}
        use_case = desired_output.get("use_case") or "general"
        quality_priority = desired_output.get("quality_priority") or "balanced"
        key = f"{use_case}:{quality_priority}"

        target_faces = request.get("target_faces")
        if target_faces is None:
            target_faces = (event.get("quality_meta", {}) or {}).get("target_faces_used")
        if target_faces is None:
            target_faces = (event.get("optimized_stats", {}) or {}).get("face_count", 0)

        bucket = grouped.setdefault(
            key,
            {
                "use_case": use_case,
                "quality_priority": quality_priority,
                "sample_count": 0,
                "target_faces_total": 0,
                "preserve_shape_true": 0,
                "preserve_vertices_true": 0,
                "preserve_faces_true": 0,
            },
        )

        bucket["sample_count"] += 1
        bucket["target_faces_total"] += int(target_faces or 0)
        bucket["preserve_shape_true"] += 1 if feedback.get("preserve_shape") else 0
        bucket["preserve_vertices_true"] += 1 if feedback.get("preserve_vertices") else 0
        bucket["preserve_faces_true"] += 1 if feedback.get("preserve_faces") else 0
        used_samples += 1

    profiles = []
    for bucket in grouped.values():
        count = max(bucket["sample_count"], 1)
        profiles.append(
            {
                "use_case": bucket["use_case"],
                "quality_priority": bucket["quality_priority"],
                "sample_count": bucket["sample_count"],
                "recommended_target_faces": int(round(bucket["target_faces_total"] / count)),
                "preserve_shape": bucket["preserve_shape_true"] / count >= 0.5,
                "preserve_vertices": bucket["preserve_vertices_true"] / count >= 0.5,
                "preserve_faces": bucket["preserve_faces_true"] / count >= 0.5,
            }
        )

    model_payload = {
        "generated_at_utc": _utc_now(),
        "training_samples_used": used_samples,
        "profiles": sorted(profiles, key=lambda item: item["sample_count"], reverse=True),
    }

    with open(PREFERENCE_MODEL_FILE, "w", encoding="utf-8") as f:
        json.dump(model_payload, f, ensure_ascii=True, indent=2)

    return model_payload


def load_preference_model() -> dict | None:
    if not PREFERENCE_MODEL_FILE.exists():
        return None
    try:
        with open(PREFERENCE_MODEL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        return None
    return None


def find_preference_profile(use_case: str, quality_priority: str) -> dict | None:
    model = load_preference_model()
    if not model:
        return None

    profiles = model.get("profiles")
    if not isinstance(profiles, list):
        return None

    # Prefer exact match first.
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        if profile.get("use_case") == use_case and profile.get("quality_priority") == quality_priority:
            return profile

    # Fallbacks in order of relevance.
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        if profile.get("use_case") == use_case:
            return profile

    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        if profile.get("quality_priority") == quality_priority:
            return profile

    return None
