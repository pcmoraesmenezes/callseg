from call_segmenter.monitoring import DriftBaseline, evaluate_window
from call_segmenter.monitoring.drift import DriftWindow

MIX = {"automotive": 0.28, "home_service": 0.41, "medicare": 0.31}
BASELINE = DriftBaseline(low_confidence_rate=0.036, ambiguous_rate=0.10, mean_probability=0.99, sector_mix=MIX)


def window(**changes):
    values = {
        "calls": 200,
        "low_confidence_rate": 0.03,
        "ambiguous_rate": 0.10,
        "mean_probability": 0.988,
        "sector_mix": MIX,
    }
    return DriftWindow(**{**values, **changes})


def test_traffic_like_the_baseline_raises_no_alert():
    assert evaluate_window(BASELINE, window()).status == "ok"


def test_a_flood_of_a_single_sector_is_flagged_by_the_mix():
    report = evaluate_window(BASELINE, window(sector_mix={"automotive": 0.95, "home_service": 0.03, "medicare": 0.02}))
    assert report.status == "alerta" and any("mistura" in alert for alert in report.alerts)


def test_a_jump_in_fragile_assignments_is_flagged_only_with_enough_evidence():
    assert evaluate_window(BASELINE, window(ambiguous_rate=0.25)).status == "alerta"
    assert (
        evaluate_window(BASELINE, window(calls=10, ambiguous_rate=0.5)).status == "amostra pequena demais para decidir"
    )


def test_a_drop_in_mean_confidence_is_flagged():
    report = evaluate_window(BASELINE, window(mean_probability=0.80))
    assert any("confiança média" in alert for alert in report.alerts)


def test_a_rise_in_low_confidence_calls_is_flagged():
    report = evaluate_window(BASELINE, window(calls=270, low_confidence_rate=0.11, mean_probability=0.958))
    assert report.status == "alerta" and any("baixa confiança" in alert for alert in report.alerts)


def test_traffic_better_than_the_baseline_is_quiet():
    assert evaluate_window(BASELINE, window(low_confidence_rate=0.0)).status == "ok"
