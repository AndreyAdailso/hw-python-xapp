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
Manager responsible for building and sending E2SM-RC v3.01 RICcontrolRequest messages.
"""

from ricxappframe.xapp_frame import RMRXapp, rmr
from ._BaseManager import _BaseManager
from ..utils.constants import Constants
from ..asn1.e2ap import E2AP_PDU_Descriptions
from ..asn1 import pycrate_recursion_fix  # noqa: F401  (recursive RANParameter types)
from ..asn1.rc import E2SM_RC_IEs


class ControlManager(_BaseManager):

    def __init__(self, rmr_xapp: RMRXapp, ric_instance_id: int = 1):
        super().__init__(rmr_xapp)
        # ricInstanceID dos RICcontrolRequest. O e2term usa este valor como RMR sub_id do
        # ACK/FAILURE; com a rota 12041/12042|<id> registrada pelo ControlRouteManager,
        # o retorno chega so a este xApp.
        self.ric_instance_id = int(ric_instance_id)

    def encode_control_header(self, amf_ue_ngap_id: int = 1,
                              style_type: int = Constants.RC_STYLE_TYPE_RADIO_RESOURCE_ALLOCATION,
                              action_id: int = Constants.RC_ACTION_ID_SLICE_PRB_QUOTA) -> bytes:
        """
        Encodes E2SM-RC Control Header Format 1.
        Default: Style 2 (Radio Resource Allocation Control), Action 6 (Slice-level PRB quota),
        as defined in O-RAN.WG3.E2SM-RC v03.00 section 7.6.3.
        """
        header = E2SM_RC_IEs.E2SM_RC_ControlHeader
        hdr_val = {
            'ric-controlHeader-formats': ('controlHeader-Format1', {
                'ueID': ('gNB-UEID', {
                    'amf-UE-NGAP-ID': amf_ue_ngap_id,
                    'guami': {
                        'pLMNIdentity': b'\x00\x01\x02',
                        'aMFRegionID': (1, 8),
                        'aMFSetID': (1, 10),
                        'aMFPointer': (1, 6)
                    }
                }),
                'ric-Style-Type': style_type,
                'ric-ControlAction-ID': action_id,
                'ric-ControlDecision': 'accept'
            })
        }
        header.set_val(hdr_val)
        return header.to_aper()

    @staticmethod
    def _element(param_id: int, value) -> dict:
        return {
            'ranParameter-ID': param_id,
            'ranParameter-valueType': ('ranP-Choice-ElementFalse', {
                'ranParameter-value': value
            })
        }

    @staticmethod
    def _structure(param_id: int, items: list) -> dict:
        return {
            'ranParameter-ID': param_id,
            'ranParameter-valueType': ('ranP-Choice-Structure', {
                'ranParameter-Structure': {'sequence-of-ranParameters': items}
            })
        }

    @staticmethod
    def _list(param_id: int, structures: list) -> dict:
        return {
            'ranParameter-ID': param_id,
            'ranParameter-valueType': ('ranP-Choice-List', {
                'ranParameter-List': {
                    'list-of-ranParameter': [{'sequence-of-ranParameters': s} for s in structures]
                }
            })
        }

    def encode_control_message(self, slice_quotas: list) -> bytes:
        """
        Encodes E2SM-RC Control Message Format 1 for Slice-level PRB quota, following the
        RAN Parameter hierarchy of O-RAN.WG3.E2SM-RC v03.00 section 8.4.3.6:

        1 RRM Policy Ratio List
          2 RRM Policy Ratio Group (one per slice)
            3 RRM Policy
              5 RRM Policy Member List
                6 RRM Policy Member
                  7 PLMN Identity (optional here)
                  8 S-NSSAI: 9 SST, 10 SD (optional)
            11 Min PRB Policy Ratio
            12 Max PRB Policy Ratio
            13 Dedicated PRB Policy Ratio
        """
        C = Constants
        groups = []
        for policy in slice_quotas:
            sst = int(policy.get("sst", 1))
            max_prb = int(policy.get("max_prb", 100))
            min_prb = int(policy.get("min_prb", 0))
            dedicated_prb = int(policy.get("dedicated_prb", 0))
            sd = policy.get("sd")
            plmn = policy.get("plmn", C.RC_PLMN_IDENTITY)

            snssai = [self._element(C.RC_PARAM_SST, ('valueOctS', bytes([sst])))]
            if sd is not None:
                snssai.append(self._element(C.RC_PARAM_SD, ('valueOctS', int(sd).to_bytes(3, 'big'))))

            member = []
            if plmn:
                plmn_bytes = bytes.fromhex(plmn) if isinstance(plmn, str) else bytes(plmn)
                member.append(self._element(C.RC_PARAM_PLMN_IDENTITY, ('valueOctS', plmn_bytes)))
            member.append(self._structure(C.RC_PARAM_S_NSSAI, snssai))

            rrm_policy = self._structure(C.RC_PARAM_RRM_POLICY, [
                self._list(C.RC_PARAM_RRM_POLICY_MEMBER_LIST, [member])
            ])

            groups.append([
                rrm_policy,
                self._element(C.RC_PARAM_MIN_PRB_RATIO, ('valueInt', min_prb)),
                self._element(C.RC_PARAM_MAX_PRB_RATIO, ('valueInt', max_prb)),
                self._element(C.RC_PARAM_DEDICATED_PRB_RATIO, ('valueInt', dedicated_prb)),
            ])

        message = E2SM_RC_IEs.E2SM_RC_ControlMessage
        msg_val = {
            'ric-controlMessage-formats': ('controlMessage-Format1', {
                'ranP-List': [self._list(C.RC_PARAM_RRM_POLICY_RATIO_LIST, groups)]
            })
        }
        message.set_val(msg_val)
        return message.to_aper()

    def build_control_request_pdu(self, slice_quotas: list) -> bytes:
        """
        Builds and encodes a standard E2AP RICcontrolRequest PDU carrying
        E2SM-RC v3.01 Control Header (Format 1) and Control Message (Format 1).
        """
        header_bytes = self.encode_control_header(
            amf_ue_ngap_id=1,
            style_type=Constants.RC_STYLE_TYPE_RADIO_RESOURCE_ALLOCATION,
            action_id=Constants.RC_ACTION_ID_SLICE_PRB_QUOTA
        )

        message_bytes = self.encode_control_message(slice_quotas)

        pdu_val = ('initiatingMessage', {
            'procedureCode': 4,
            'criticality': 'ignore',
            'value': ('RICcontrolRequest', {
                'protocolIEs': [
                    {'id': 29, 'criticality': 'reject', 'value': ('RICrequestID', {'ricRequestorID': 1001, 'ricInstanceID': self.ric_instance_id})},
                    {'id': 5,  'criticality': 'reject', 'value': ('RANfunctionID', Constants.RC_RAN_FUNCTION_ID)},
                    {'id': 22, 'criticality': 'reject', 'value': ('RICcontrolHeader', header_bytes)},
                    {'id': 23, 'criticality': 'reject', 'value': ('RICcontrolMessage', message_bytes)},
                    {'id': 21, 'criticality': 'reject', 'value': ('RICcontrolAckRequest', 'ack')},
                ]
            })
        })

        pdu = E2AP_PDU_Descriptions.E2AP_PDU
        pdu.set_val(pdu_val)
        return pdu.to_aper()

    def send_control_request(self, meid: str, slice_quotas: list) -> bool:
        """
        Sends an E2SM-RC slicing control request to a target gNB via RMR.
        """
        # Visual Logging
        self.logger.info("======================================================================")
        self.logger.info(f"[RC-CONTROL-COMMAND] Enviando RICcontrolRequest -> Node: {meid}")
        self.logger.info("----------------------------------------------------------------------")
        self.logger.info(f"  RANFunctionID: {Constants.RC_RAN_FUNCTION_ID} | Style: {Constants.RC_STYLE_TYPE_RADIO_RESOURCE_ALLOCATION} | ActionID: {Constants.RC_ACTION_ID_SLICE_PRB_QUOTA} (Slice PRB Quota)")
        for q in slice_quotas:
            sst = q.get("sst", 1)
            name = "eMBB" if sst == 1 else ("URLLC" if sst == 2 else f"Slice-{sst}")
            max_prb = q.get("max_prb", 100)
            ded_prb = q.get("dedicated_prb", 0)
            min_prb = q.get("min_prb", 0)
            self.logger.info(f"  - Slice (SST={sst}, {name:<5}): MaxPRB = {max_prb:>2}%, Dedicated = {ded_prb:>2}%, MinPRB = {min_prb:>2}%")
        self.logger.info("======================================================================")

        try:
            payload = self.build_control_request_pdu(slice_quotas)
            node_meid_bytes = bytes(meid, "utf-8") if isinstance(meid, str) else meid

            sbuf = rmr.rmr_alloc_msg(
                vctx=self._rmr_xapp._mrc,
                size=len(payload),
                payload=payload,
                gen_transaction_id=True,
                mtype=Constants.RIC_CONTROL_REQ
            )
            rmr.rmr_set_meid(sbuf, node_meid_bytes)

            for _ in range(50):
                sbuf = rmr.rmr_send_msg(self._rmr_xapp._mrc, sbuf)
                if sbuf.contents.state == 0:
                    self._rmr_xapp.rmr_free(sbuf)
                    self.logger.info(f"[RC-CONTROL-COMMAND] Mensagem enviada com sucesso para {meid}.")
                    return True

            self._rmr_xapp.rmr_free(sbuf)
            self.logger.warning(f"[RC-CONTROL-COMMAND] Timeout/Falha ao enviar mensagem para {meid}.")
            return False

        except Exception as e:
            self.logger.error(f"[RC-CONTROL-COMMAND] Erro ao enviar comando de controle para {meid}: {e}")
            return False
