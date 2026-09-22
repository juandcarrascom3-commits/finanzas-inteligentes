from datetime import date

from backend.analytics.understand import expand_financial_events, get_recurring_transactions


def tx(id, amount, day, description="Netflix", category="General", account_id="acc", currency="USD", flow_type="EXPENSE"):
    return {
        "id": id,
        "amount": amount,
        "date": day,
        "description": description,
        "category": category,
        "account_id": account_id,
        "currency": currency,
        "flow_type": flow_type,
        "source": "MANUAL",
    }


def first_pattern(rows):
    return get_recurring_transactions(rows, today=date(2026, 10, 1))[0]


def test_monthly_same_day_next_occurrence():
    pattern = first_pattern([tx("1", -100, "2026-06-15"), tx("2", -101, "2026-07-15"), tx("3", -99, "2026-08-15"), tx("4", -100, "2026-09-15")])
    assert pattern["frequency"] == "MONTHLY"
    assert pattern["monthly_anchor"] == "SAME_DAY_OF_MONTH"
    assert pattern["next_expected_date"] == "2026-10-15"


def test_end_of_month_and_leap_year_eom_are_preserved():
    pattern = first_pattern([tx("1", -100, "2026-01-31"), tx("2", -102, "2026-02-28"), tx("3", -101, "2026-03-31"), tx("4", -99, "2026-04-30")])
    assert pattern["frequency"] == "MONTHLY"
    assert pattern["monthly_anchor"] == "END_OF_MONTH"
    assert pattern["next_expected_date"] == "2026-05-31"

    leap = first_pattern([tx("1", -100, "2028-01-31"), tx("2", -100, "2028-02-29"), tx("3", -100, "2028-03-31")])
    assert leap["monthly_anchor"] == "END_OF_MONTH"
    assert leap["next_expected_date"] == "2028-04-30"


def test_weekly_and_biweekly_classification():
    weekly = first_pattern([tx("1", -100, "2026-09-01"), tx("2", -100, "2026-09-08"), tx("3", -100, "2026-09-15"), tx("4", -100, "2026-09-22")])
    assert weekly["frequency"] == "WEEKLY"
    assert weekly["typical_interval_days"] == 7

    biweekly = first_pattern([tx("1", -100, "2026-09-01"), tx("2", -100, "2026-09-15"), tx("3", -100, "2026-09-29")])
    assert biweekly["frequency"] == "BIWEEKLY"
    assert biweekly["typical_interval_days"] == 14


def test_robust_amount_outlier_and_variable_monthly_amount():
    outlier = first_pattern([tx("1", -100, "2026-05-01"), tx("2", -102, "2026-06-01"), tx("3", -500, "2026-07-01"), tx("4", -99, "2026-08-01"), tx("5", -101, "2026-09-01")])
    assert outlier["typical_amount"] == -101
    assert outlier["amount_mad"] == 1

    variable = first_pattern([tx("1", -98000, "2026-06-15"), tx("2", -102000, "2026-07-15"), tx("3", -100000, "2026-08-15"), tx("4", -101000, "2026-09-15")])
    assert variable["frequency"] == "MONTHLY"
    assert variable["confidence"] in {"MEDIUM", "HIGH"}


def test_sparse_history_is_low_confidence():
    pattern = first_pattern([tx("1", -100, "2026-08-01"), tx("2", -100, "2026-09-01")])
    assert pattern["confidence"] == "LOW"


def test_currency_direction_and_context_isolation():
    rows = [
        tx("u1", -100, "2026-07-01", currency="USD"),
        tx("u2", -100, "2026-08-01", currency="USD"),
        tx("u3", -100, "2026-09-01", currency="USD"),
        tx("c1", -100, "2026-07-01", currency="COP"),
        tx("c2", -100, "2026-08-01", currency="COP"),
        tx("c3", -100, "2026-09-01", currency="COP"),
        tx("i1", 100, "2026-07-01", currency="USD", flow_type="INCOME"),
        tx("i2", 100, "2026-08-01", currency="USD", flow_type="INCOME"),
        tx("i3", 100, "2026-09-01", currency="USD", flow_type="INCOME"),
        tx("a1", -100, "2026-07-01", account_id="other"),
        tx("a2", -100, "2026-08-01", account_id="other"),
        tx("a3", -100, "2026-09-01", account_id="other"),
    ]
    patterns = get_recurring_transactions(rows, today=date(2026, 10, 1))
    assert len(patterns) == 4
    assert {p["currency"] for p in patterns} == {"USD", "COP"}
    assert {p["direction"] for p in patterns} == {"INFLOW", "OUTFLOW"}
    assert len({p["account_id"] for p in patterns if p["currency"] == "USD" and p["direction"] == "OUTFLOW"}) == 2


def test_transfers_do_not_create_canonical_events():
    rows = [tx("1", -100, "2026-07-01", flow_type="TRANSFER"), tx("2", -100, "2026-08-01", flow_type="TRANSFER"), tx("3", -100, "2026-09-01", flow_type="TRANSFER")]
    patterns = get_recurring_transactions(rows, today=date(2026, 10, 1))
    assert patterns == []
    assert expand_financial_events(patterns, date(2026, 10, 1), date(2026, 10, 31)) == []


def test_range_expansion_is_bounded_deterministic_and_excludes_low():
    high = first_pattern([tx("1", -100, "2026-09-01"), tx("2", -100, "2026-09-08"), tx("3", -100, "2026-09-15"), tx("4", -100, "2026-09-22")])
    low = first_pattern([tx("l1", -100, "2026-08-01", description="Gym"), tx("l2", -100, "2026-09-01", description="Gym")])
    events = expand_financial_events([high, low], date(2026, 9, 23), date(2026, 10, 14))
    assert [event["date"] for event in events] == ["2026-09-29", "2026-10-06", "2026-10-13"]
    assert all(event["certainty"] == "EXPECTED" for event in events)
    assert events == expand_financial_events([high, low], date(2026, 9, 23), date(2026, 10, 14))
