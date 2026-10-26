# Test cases implemented in Sprint 1

| ID | Requirement | Test |
|---|---|---|
| TC-VDC-01 | Classification accuracy at least 90% | `tests/unit/detection/test_classifier_and_synthetic.py` |
| TC-VDC-02 | Counts within 5% of ground truth | `tests/unit/detection/test_counting_and_pedestrians.py` |
| TC-VDC-03 | Pedestrian served within one cycle | `tests/unit/signal_control/test_adaptive_controller.py` |
| TC-Sig-01 | Green time adapts within one cycle | same file |
| TC-Sig-02 | Override applied within 2 s, interlock | `tests/unit/signal_control/test_override_and_audit.py` |
| TC-Sig-03 | Audit log has every state change | same file |
| TC-Sim-01/02/03 | Network validation, repeatable runs, metrics under 5 s | `tests/unit/simulation/test_engine_and_networks.py` |
| TC-Adm-01 | Analyst cannot override signals | `tests/unit/signal_control/test_signal_api.py` |
| TC-Adm-02..04 | Login, roles, configuration changes | `tests/unit/admin/` |
| TC-Sec-01 | TLS 1.2 minimum | `tests/security/test_tls_minimum_version.py` |
| Integration | Sensor to controller to audit, RBAC across modules | `tests/integration/test_sprint1_flows.py` |
