"""Locks in the step 3b manual verification of three randomly picked units (seed 482992)."""

from scripts.models import DependencyKind, RiskKind, Visibility


def unit(catalog, unit_id):
    return next(s for s in catalog.subprograms() if s.unit_id == unit_id)


def edges(graph, kind, **match):
    return {(e.source, e.target, e.line) for e in graph.edges
            if e.kind == kind and all(getattr(e, k) == v for k, v in match.items())}


def accesses(usage, unit_id):
    return {(a.operation.value, a.relation, a.line) for a in usage.accesses if a.unit_id == unit_id}


def flags(risks, unit_id):
    return {(f.kind, f.line) for f in risks.flags if f.unit_id == unit_id}


def test_set_status(legacy):
    catalog, graph, usage, risks = legacy
    u = unit(catalog, "PKG_ORDER.SET_STATUS")
    assert u.signature == "PROCEDURE SET_STATUS(P_ORD_ID IN NUMBER, P_STATUS IN NUMBER)"
    assert u.visibility == Visibility.PUBLIC
    assert (u.spec_ref.start_line, u.spec_ref.end_line) == (21, 21)
    assert (u.body_ref.start_line, u.body_ref.end_line) == (98, 104)
    assert edges(graph, DependencyKind.CALL, source=u.unit_id) == {(u.unit_id, "PKG_ORDER.WLOG", 102)}
    assert {(s, ln) for s, _, ln in edges(graph, DependencyKind.CALL, target=u.unit_id)} == {
        ("INV_API.CANCEL_INVOICE", 147),
        ("INV_API.CREATE_INVOICE#2", 119),
        ("PKG_ORDER.PROCESS_ORDER", 172),
        ("PKG_ORDER.PROCESS_ORDER", 175),
        ("PKG_ORDER.PROCESS_ORDER", 185),
        ("PKG_ORDER.PROCESS_ORDER", 233),
    }
    assert accesses(usage, u.unit_id) == {("UPDATE", "ORDERS", 100)}
    assert flags(risks, u.unit_id) == set()


def test_unblock_customer(legacy):
    catalog, graph, usage, risks = legacy
    u = unit(catalog, "CUST_MGMT.UNBLOCK_CUSTOMER")
    assert u.signature == "PROCEDURE UNBLOCK_CUSTOMER(P_CUST_ID IN NUMBER)"
    assert (u.body_ref.start_line, u.body_ref.end_line) == (117, 127)
    assert edges(graph, DependencyKind.CALL, source=u.unit_id) == {(u.unit_id, "UTIL_LOG.LOG_MSG", 126)}
    assert edges(graph, DependencyKind.CALL, target=u.unit_id) == set()
    assert accesses(usage, u.unit_id) == {("UPDATE", "CUSTOMERS", 120)}
    assert flags(risks, u.unit_id) == {
        (RiskKind.NO_CALLER, 117),
        (RiskKind.HARDCODED_VALUE, 121),
        (RiskKind.HARDCODED_VALUE, 124),
    }
    # Gap found in the spot check: the UPDATE fires TRG_CUST_BIU.
    assert edges(graph, DependencyKind.FIRES_TRIGGER, source=u.unit_id) == {
        (u.unit_id, "TRG_CUST_BIU", 120)
    }


def test_send_reminders(legacy):
    catalog, graph, usage, risks = legacy
    u = unit(catalog, "INV_API.SEND_REMINDERS")
    assert u.signature == "PROCEDURE SEND_REMINDERS"
    assert u.params == []
    assert (u.body_ref.start_line, u.body_ref.end_line) == (224, 246)
    assert {(t, ln) for _, t, ln in edges(graph, DependencyKind.CALL, source=u.unit_id)} == {
        ("CUST_MGMT.GET_CUST_ATTR", 230),
        ("UTIL_LOG.LOG_MSG", 234),
        ("UTIL_LOG.FMT_AMT", 235),
        ("CUST_MGMT.CHK_OVERDUE_CUSTOMERS", 245),
    }
    assert {s for s, _, _ in edges(graph, DependencyKind.CALL, target=u.unit_id)} == {"UTIL_LOG.HOUSEKEEPING"}
    assert accesses(usage, u.unit_id) == {("SELECT", "V_OPEN_INVOICES", 228), ("UPDATE", "INVOICES", 237)}
    assert flags(risks, u.unit_id) == {(RiskKind.HARDCODED_VALUE, 229), (RiskKind.COMMIT, 243)}


def test_fires_trigger_edges(legacy):
    _, graph, _, _ = legacy
    assert {(s, t) for s, t, _ in edges(graph, DependencyKind.FIRES_TRIGGER)} == {
        ("CUST_MGMT.BLOCK_CUSTOMER", "TRG_CUST_BIU"),
        ("CUST_MGMT.CREATE_CUSTOMER", "TRG_CUST_BIU"),
        ("CUST_MGMT.MERGE_CUST", "TRG_CUST_BIU"),
        ("CUST_MGMT.UNBLOCK_CUSTOMER", "TRG_CUST_BIU"),
        ("CUST_MGMT.UPD_CREDIT_LIMIT", "TRG_CUST_BIU"),
        ("INV_API.REGISTER_PAYMENT", "TRG_PAY_AIR"),
        ("PKG_ORDER.ADD_LINE#2", "TRG_ORDL_AIUD"),
    }


def test_counts(legacy):
    catalog, _, _, _ = legacy
    subs = catalog.subprograms()
    assert len(catalog.packages) == 4
    assert len(subs) == 43
    assert sum(s.visibility == Visibility.PUBLIC for s in subs) == 36
    assert (len(catalog.tables), len(catalog.views), len(catalog.triggers), len(catalog.sequences)) == (10, 3, 3, 5)
