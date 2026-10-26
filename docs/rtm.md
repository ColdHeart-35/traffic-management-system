# Requirements traceability (Sprint 1)

| Requirement | Code | Tests |
|---|---|---|
| TMS-F-001 adaptive timing | `signal_control/controller.py` | TC-Sig-01 |
| TMS-F-002 manual override | `signal_control/override.py`, `api.py` | TC-Sig-02, TC-Adm-01 |
| TMS-F-003 audit log | `signal_control/audit.py` | TC-Sig-03 |
| TMS-F-006 classification | `detection/classifier.py` | TC-VDC-01 |
| TMS-F-007 counts and density | `detection/counter.py` | TC-VDC-02 |
| TMS-F-008 pedestrian requests | `detection/pedestrian.py`, controller | TC-VDC-03 |
| TMS-F-009/010/011 simulation | `simulation/` | TC-Sim-01..03 |
| TMS-F-018 RBAC | `admin/rbac.py` | TC-Adm-01..03 |
| TMS-F-019 configuration | `admin/config_service.py` | TC-Adm-04 |
| PRJ-SR-001 TLS | `infra/tls.py` | TC-Sec-01 |
| Sprint 2 (F-004/5/12-17, NF-*, SR-002/3/5) | not yet built | not yet written |
