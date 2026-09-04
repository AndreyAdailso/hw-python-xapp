# ==================================================================================
#
#       Copyright (c) 2020 Samsung Electronics Co., Ltd. All Rights Reserved.
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

import threading
from os import getenv
from ricxappframe.xapp_frame import RMRXapp, rmr


from .utils.constants import Constants
from .manager import *

from .handler import *
from mdclogpy import Logger
import time


class HWXapp:

    def __init__(self):
        fake_sdl = getenv("USE_FAKE_SDL", False)
        self._shutdown = False
        self._control_mgr = None
        self._sub_mgr = None
        self._control_thread = None
        self._rmr_xapp = RMRXapp(self._default_handler,
                                 config_handler=self._handle_config_change,
                                 rmr_port=4560,
                                 post_init=self._post_init,
                                 use_fake_sdl=bool(fake_sdl))

    def _post_init(self, rmr_xapp):
        """
        Function that runs when xapp initialization is complete
        """
        rmr_xapp.logger.mdclog_format_init()
        time.sleep(5)   # wait for xApp to get registered and routes are updated
        rmr_xapp.logger.info("HWXapp.post_init :: post_init called")

        sdl_mgr = SdlManager(rmr_xapp)
        sdl_mgr.sdlGetNodeBList()

        self._sub_mgr = SubscriptionManager(rmr_xapp)
        self._control_mgr = ControlManager(rmr_xapp)

        # 1. Enviar subscrição KPM (RANFunctionID=200) para todos os nós E2 registrados
        enb_list = self._sub_mgr.get_enb_list()
        for enb in enb_list:
            enb_id = enb.inventory_name
            rmr_xapp.logger.info(f"HWXapp.post_init :: Subscribing to eNB: {enb_id}")
            self._sub_mgr.send_subscription_request(enb_id)

        gnb_list = self._sub_mgr.get_gnb_list()
        for gnb in gnb_list:
            gnb_id = gnb.inventory_name
            rmr_xapp.logger.info(f"HWXapp.post_init :: Subscribing to gNB: {gnb_id}")
            self._sub_mgr.send_subscription_request(gnb_id)

        # 2. Iniciar thread de controle periódico RC (alterna quotas a cada 10s)
        self._control_thread = threading.Thread(target=self._run_slicing_control_loop, args=(rmr_xapp,), daemon=True)
        self._control_thread.start()
        rmr_xapp.logger.info("HWXapp.post_init :: RC Slicing Control Thread iniciada.")

    def _run_slicing_control_loop(self, rmr_xapp):
        """
        Thread de controle de fatiamento: alterna a cada 10 segundos as quotas de PRB entre:
          - Estado A: Slice 1 (eMBB, SST=1) = 80%, Slice 2 (URLLC, SST=2) = 20%
          - Estado B: Slice 1 (eMBB, SST=1) = 20%, Slice 2 (URLLC, SST=2) = 80%
        """
        rmr_xapp.logger.info("HWXapp::_run_slicing_control_loop loop iniciado com ciclo de 10s.")
        state_toggle = True  # True: 80/20 | False: 20/80

        while not self._shutdown:
            time.sleep(10)
            if self._shutdown:
                break

            if state_toggle:
                # Estado A: 80% eMBB / 20% URLLC
                quotas = [
                    {"sst": 1, "max_prb": 80, "dedicated_prb": 80, "min_prb": 80},
                    {"sst": 2, "max_prb": 20, "dedicated_prb": 20, "min_prb": 20},
                ]
                state_name = "Estado A (eMBB: 80% PRB | URLLC: 20% PRB)"
            else:
                # Estado B: 20% eMBB / 80% URLLC
                quotas = [
                    {"sst": 1, "max_prb": 20, "dedicated_prb": 20, "min_prb": 20},
                    {"sst": 2, "max_prb": 80, "dedicated_prb": 80, "min_prb": 80},
                ]
                state_name = "Estado B (eMBB: 20% PRB | URLLC: 80% PRB)"

            gnb_list = self._sub_mgr.get_gnb_list() if self._sub_mgr else []
            if not gnb_list:
                rmr_xapp.logger.warning(f"[RC-LOOP] Nenhum gNB registrado no momento para aplicar {state_name}.")
                continue

            rmr_xapp.logger.info(f"\n>>> [RC-CYCLE] Alternando quotas de fatiamento para: {state_name} <<<")
            for gnb in gnb_list:
                gnb_id = gnb.inventory_name
                self._control_mgr.send_control_request(gnb_id, quotas)

            state_toggle = not state_toggle

    def _handle_config_change(self, rmr_xapp, config):
        """
        Function that runs at start and on every configuration file change.
        """
        rmr_xapp.logger.info("HWXapp.handle_config_change:: config: {}".format(config))
        rmr_xapp.config = config  # No mutex required due to GIL

    def _default_handler(self, rmr_xapp, summary, sbuf):
        """
        Function that processes messages for which no handler is defined
        """
        rmr_xapp.logger.info("HWXapp.default_handler called for msg type = " +
                                   str(summary[rmr.RMR_MS_MSG_TYPE]))
        rmr_xapp.rmr_free(sbuf)

    def createHandlers(self):
        """
        Function that creates all the handlers for RMR Messages
        """
        HealthCheckHandler(self._rmr_xapp, Constants.RIC_HEALTH_CHECK_REQ)
        A1PolicyHandler(self._rmr_xapp, Constants.A1_POLICY_REQ)
        SubscriptionHandler(self._rmr_xapp, Constants.SUBSCRIPTION_REQ)
        IndicationHandler(self._rmr_xapp, Constants.RIC_INDICATION)
        ControlHandler(self._rmr_xapp, Constants.RIC_CONTROL_ACK)
        ControlHandler(self._rmr_xapp, Constants.RIC_CONTROL_FAILURE)

    def start(self, thread=False):
        """
        This is a convenience function that allows this xapp to run in Docker
        for "real" (no thread, real SDL), but also easily modified for unit testing
        (e.g., use_fake_sdl). The defaults for this function are for the Dockerized xapp.
        """
        self.createHandlers()
        self._rmr_xapp.run(thread)

    def stop(self):
        """
        can only be called if thread=True when started
        """
        self._rmr_xapp.logger.info("Shutting down hw-python xApp...")
        self._shutdown = True
        if self._sub_mgr:
            self._sub_mgr.unsubscribe()
        self._rmr_xapp.stop()

