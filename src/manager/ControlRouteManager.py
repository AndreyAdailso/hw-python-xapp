# ==================================================================================
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#          http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ==================================================================================
"""
ControlRouteManager.

Keeps the RMR routes for RIC_CONTROL_ACK (12041) and RIC_CONTROL_FAILURE (12042)
pointing to this xApp.

Why this is needed
------------------
* rtmgr (0.9.x, including master) generates ``RIC_CONTROL_ACK|-1`` and
  ``RIC_CONTROL_FAILURE|-1`` routes for *every* deployed xApp, regardless of the
  xApp descriptor. With more than one xApp the entries collide and RMR keeps
  only one of them, so the ACK may be delivered to another xApp (e.g. the KPM
  xApp).
* e2term sets the RMR ``sub_id`` of the ACK/FAILURE to the ``ricInstanceID`` of
  the original RICcontrolRequest. RMR looks up ``(mtype, sub_id)`` before
  falling back to ``(mtype, -1)``.
* rtmgr creates ``RIC_CONTROL_ACK|<id>`` and ``RIC_CONTROL_FAILURE|<id>`` routes
  for each entry registered through
  ``POST /ric/v1/handles/xapp-subscription-handle`` (the same API used by
  submgr).

This manager registers ``subscription_id = ric_instance_id`` for this xApp's RMR
endpoint, so the ACK/FAILURE of our control requests is routed only here. The
``ric_instance_id`` must be outside the submgr allocation range (1..65534) and
unique among the xApps that send RIC Control requests.

The registration is retried until rtmgr knows the xApp endpoint (HTTP 400 until
appmgr registration propagates) and re-asserted periodically, because rtmgr
keeps it only in memory (lost on rtmgr restart). The POST is idempotent.
"""

import json
import threading
import urllib.error
import urllib.request

from ricxappframe.xapp_frame import RMRXapp

from ._BaseManager import _BaseManager


class ControlRouteManager(_BaseManager):
    """Registers and maintains the subid-specific RIC Control outcome routes."""

    REGISTER_PATH = "/ric/v1/handles/xapp-subscription-handle"

    def __init__(self, rmr_xapp: RMRXapp, xapp_name: str, config: dict = None):
        super().__init__(rmr_xapp)
        cfg = config or {}
        namespace = cfg.get("xapp_namespace", "ricxapp")

        self.enabled = bool(cfg.get("enabled", True))
        self.ric_instance_id = int(cfg.get("ric_instance_id", 65535))
        self.rtmgr_url = cfg.get(
            "rtmgr_url", "http://service-ricplt-rtmgr-http.ricplt:3800"
        ).rstrip("/")
        self.rmr_address = cfg.get(
            "rmr_service", f"service-{namespace}-{xapp_name}-rmr.{namespace}"
        )
        self.rmr_port = int(cfg.get("rmr_port", 4560))
        self.retry_seconds = max(1, int(cfg.get("retry_seconds", 10)))
        self.refresh_seconds = max(self.retry_seconds, int(cfg.get("refresh_seconds", 60)))
        self.timeout_seconds = float(cfg.get("timeout_seconds", 5))

        self._stop_event = threading.Event()
        self._thread = None
        self._registered = False

    # ------------------------------------------------------------------ helpers
    def _body(self) -> bytes:
        return json.dumps(
            {
                "address": self.rmr_address,
                "port": self.rmr_port,
                "subscription_id": self.ric_instance_id,
            }
        ).encode("utf-8")

    def _request(self, method: str):
        """Send the registration request; return (http_status, response_text)."""
        req = urllib.request.Request(
            self.rtmgr_url + self.REGISTER_PATH,
            data=self._body(),
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
        except Exception as e:  # connection refused, DNS, timeout
            return None, str(e)

    # --------------------------------------------------------------- public API
    def register(self) -> bool:
        """Register (or re-assert) the control outcome routes. Idempotent."""
        status, text = self._request("POST")
        ok = status is not None and 200 <= status < 300
        target = f"{self.rmr_address}:{self.rmr_port}"
        if ok:
            if not self._registered:
                self.logger.info(
                    f"ControlRouteManager: RIC_CONTROL_ACK/FAILURE routed to {target} "
                    f"with subid={self.ric_instance_id} (rtmgr HTTP {status})"
                )
            self._registered = True
        else:
            # 400 is expected until appmgr has registered this xApp in rtmgr.
            self.logger.warning(
                f"ControlRouteManager: registration of subid={self.ric_instance_id} "
                f"for {target} failed (rtmgr HTTP {status}): {text.strip()[:200]}"
            )
            self._registered = False
        return ok

    def unregister(self):
        """Remove the registration (called on graceful shutdown)."""
        if not self.enabled:
            return
        status, text = self._request("DELETE")
        self.logger.info(
            f"ControlRouteManager: unregistered subid={self.ric_instance_id} "
            f"(rtmgr HTTP {status})"
        )

    def is_registered(self) -> bool:
        return self._registered

    def _loop(self):
        while not self._stop_event.is_set():
            self.register()
            wait = self.refresh_seconds if self._registered else self.retry_seconds
            self._stop_event.wait(wait)

    def start(self):
        if not self.enabled:
            self.logger.warning(
                "ControlRouteManager disabled: RIC_CONTROL_ACK/FAILURE will rely on "
                "rtmgr default routes (subid -1), which collide when several xApps "
                "are deployed."
            )
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, name="rc-control-route", daemon=True
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.unregister()
