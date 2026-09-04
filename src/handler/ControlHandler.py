# ==================================================================================
#
#       Copyright (c) 2026 LASSE/UFPA - Universidade Federal do Pará
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
Handler for RIC Control response messages (ACK / Failure).
"""

from ricxappframe.xapp_frame import RMRXapp, rmr
from ._BaseHandler import _BaseHandler
from ..utils.constants import Constants


class ControlHandler(_BaseHandler):

    def __init__(self, rmr_xapp: RMRXapp, msgtype=Constants.RIC_CONTROL_ACK):
        super().__init__(rmr_xapp, msgtype)

    def request_handler(self, rmr_xapp, summary, sbuf):
        msg_type = summary.get(rmr.RMR_MS_MSG_TYPE, 0)
        meid = summary.get(rmr.RMR_MS_MEID, "")
        if isinstance(meid, bytes):
            meid = meid.decode("utf-8", errors="ignore").rstrip("\x00")

        if msg_type == Constants.RIC_CONTROL_ACK:
            self.logger.info(f"[RC-CONTROL-ACK] Recebida confirmação de controle (ACK) do Node: {meid}")
        elif msg_type == Constants.RIC_CONTROL_FAILURE:
            self.logger.error(f"[RC-CONTROL-FAILURE] Recebida falha de controle do Node: {meid}")
        else:
            self.logger.info(f"[RC-CONTROL-RESP] Recebida resposta de controle ({msg_type}) do Node: {meid}")

        rmr_xapp.rmr_free(sbuf)
