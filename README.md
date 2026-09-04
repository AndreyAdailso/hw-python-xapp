# O-RAN Near-RT RIC: Python xApp for E2SM-KPM and E2SM-RC Dynamic Slicing

This repository contains an advanced prototype **Python xApp** for the **Near-RT RIC (Release I / Dawn / Cherry)** based on the official O-RAN SC Python xApp Framework (`ricxappframe`).

The xApp is designed to interface directly with E2 Nodes (such as the **NORI** ns-3 simulator or live gNBs) to perform **closed-loop telemetry collection** and **real-time dynamic RAN slicing control**.

---

## 🚀 Key Features

1. **E2SM-KPM v3.00 Telemetry Collection:**
   - Automatically queries SDL / RNIB database to discover active E2 Nodes (`gnb_*`).
   - Issues `RIC_SUB_REQ` (Msg Type 12010, RANFunctionID: 200) to subscribe to radio performance metrics (`DRB.PdcpSduVolumeDL`, `RRU.PrbUsedDl`, etc.).
   - Processes periodic `RIC_INDICATION` messages (Msg Type 12050), decoding ASN.1 APER payloads in real-time.

2. **E2SM-RC v3.01 Dynamic Slice Quota Control:**
   - Implements native ASN.1 APER encoding for **E2SM-RC v3.01** using Pycrate (`E2SM_RC_ControlHeader` Format 1 and `E2SM_RC_ControlMessage` Format 1).
   - Automatically cycles slice PRB allocations every 10 seconds via `RIC_CONTROL_REQ` (Msg Type 12040, RANFunctionID: 300, Style 1, Action ID 6):
     - **Cycle A:** Slice 1 (eMBB, SST=1) = 80% PRB | Slice 2 (URLLC, SST=2) = 20% PRB
     - **Cycle B:** Slice 1 (eMBB, SST=1) = 20% PRB | Slice 2 (URLLC, SST=2) = 80% PRB
   - Handles `RIC_CONTROL_ACK` (Msg Type 12041) / `RIC_CONTROL_FAILURE`.

3. **Production Deployment & Monitoring Automation:**
   - One-command deployment script (`./update_xapp.sh`) that automates Helm chart onboarding, Docker image compilation, registry pushing, and xApp pod reinstallation via `dms_cli`.
   - Real-time formatted log streaming via `./log_xapp.sh`.

---

## 📁 Repository Structure

```
hw-python-xapp/
├── init/
│   ├── config-file.json       # xApp descriptor (RMR ports, endpoints, message types)
│   └── schema.json            # JSON schema for config-file validation
├── src/
│   ├── asn1/                  # ASN.1 schemas and pycrate compiled modules
│   │   ├── e2sm-rc-v03.01.asn # E2SM-RC v3.01 ASN.1 schema
│   │   ├── e2sm-v03.01.asn    # E2SM Common IEs schema
│   │   └── rc.py              # Compiled ASN.1 Python codecs
│   ├── handler/               # RMR message handlers
│   │   ├── ControlHandler.py  # RIC Control ACK / Failure handler
│   │   ├── IndicationHandler.py # RIC Indication / KPM telemetry decoder
│   │   └── SubscriptionHandler.py # RIC Subscription Response handler
│   ├── manager/               # Protocol managers
│   │   ├── ControlManager.py  # E2SM-RC Control Message encoder and sender
│   │   └── SubscriptionManager.py # KPM Subscription builder and sender
│   ├── utils/
│   │   └── constants.py       # RMR message types and O-RAN constants
│   ├── hwxapp.py              # Main xApp orchestrator and slicing control loop
│   └── main.py                # Entrypoint
├── update_xapp.sh             # Build, onboard, and deploy automation script
├── log_xapp.sh                # Live Kubernetes pod log viewer
├── Dockerfile                 # Multi-stage container definition
└── setup.py                   # Python package configuration
```

---

## ⚙️ Message Flow Diagram

```
  xApp (hw-python)               Near-RT RIC (RMR / E2Term)                 gNB / ns-3 (e2sim)
         │                                   │                                      │
  ───────┼─── 1. DISCOVERY & KPM SUBSCRIPTION ──────────────────────────────────────┼───────
         │                                   │                                      │
         │  1. Query SDL / RNIB              │                                      │
         │──────────────────────────────────>│                                      │
         │  (Get active gnb_268_...)         │                                      │
         │                                   │                                      │
         │  2. RIC_SUB_REQ (MsgType 12010)   │       Forward SCTP                   │
         │     [RANFunctionID = 200 (KPM)]   │─────────────────────────────────────>│
         │──────────────────────────────────>│                                      │
         │                                   │  3. RIC_SUB_RESP (MsgType 12011)     │
         │<──────────────────────────────────│<─────────────────────────────────────│
         │                                   │                                      │
  ───────┼─── 2. CONTINUOUS KPM TELEMETRY STREAM ───────────────────────────────────┼───────
         │                                   │                                      │
         │                                   │  4. RIC_INDICATION (MsgType 12050)   │
         │<──────────────────────────────────│<─────────────────────────────────────│
         │  [Decodes PDCP Volume, PRB stats] │     (Periodic reports)               │
         │                                   │                                      │
  ───────┼─── 3. PERIODIC RC CONTROL LOOP (Every 10s) ──────────────────────────────┼───────
         │                                   │                                      │
         │  5. RIC_CONTROL_REQ (Type 12040)  │       Forward SCTP                   │
         │     [RANFunctionID = 300 (RC)]    │─────────────────────────────────────>│
         │     [80% eMBB / 20% URLLC]        │                                      │ [ns-3 applies quotas
         │──────────────────────────────────>│                                      │  to MAC scheduler]
         │                                   │  6. RIC_CONTROL_ACK (Type 12041)     │
         │<──────────────────────────────────│<─────────────────────────────────────│
         │                                   │                                      │
         │   ... (10 seconds interval) ...   │                                      │
         │                                   │                                      │
         │  7. RIC_CONTROL_REQ (Type 12040)  │       Forward SCTP                   │
         │     [20% eMBB / 80% URLLC]        │─────────────────────────────────────>│
         │──────────────────────────────────>│                                      │
```

---

## 🛠️ Deployment and Execution

### 1. Prerequisites
- Kubernetes cluster with O-RAN Near-RT RIC deployed (`ricplt` namespace).
- Local docker registry running (e.g. `127.0.0.1:5001`).
- `dms_cli` installed and configured.

### 2. Deploy or Update the xApp
Execute the automated deployment script from the repository root:

```bash
./update_xapp.sh
```

This script will:
1. Onboard the Helm chart using `dms_cli`.
2. Terminate any previous `hw-python` instance.
3. Build and push the Docker image to the local registry (`127.0.0.1:5001/hw-python:1.0.0`).
4. Install the xApp chart in namespace `ricxapp`.
5. Wait for the pod to become ready and tail initial logs.

### 3. Monitoring Live Logs & Metrics
To follow the xApp output in real-time:

```bash
./log_xapp.sh
```

Or via `kubectl`:

```bash
kubectl logs -f $(kubectl get pods -n ricxapp | grep "ricxapp-hw-python-" | awk '{print $1}') -n ricxapp
```

---

## 🧪 Testing with NORI Simulator

1. Deploy the xApp using `./update_xapp.sh`.
2. Start the **NORI** ns-3 simulation with E2 interface enabled:
   ```bash
   ./ns3 run nori-rc-slicing-demo -- --ipE2TermRic="<E2TERM_IP>" --simTime=0
   ```
3. Watch the xApp logs stream KPM telemetry and issue 10-second PRB quota shifts (80%/20% ⇄ 20%/80%), and observe the dynamic throughput allocation in ns-3!

---

## 📄 License

Apache License 2.0. See [LICENSE](LICENSE) for details.
