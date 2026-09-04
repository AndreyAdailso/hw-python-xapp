# ==================================================================================
#
#       Copyright (c) 2024 Alexandre Huff. All Rights Reserved.
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
Handles indication messages from enbs and gnbs through rmr.
"""

from ricxappframe.xapp_frame import RMRXapp, rmr
from ._BaseHandler import _BaseHandler

from pycrate_asn1rt.err import ASN1ObjErr, ASN1Err
from ..asn1.e2ap import E2AP_PDU_Descriptions
from ..asn1.kpm import E2SM_KPM_IEs


class IndicationHandler(_BaseHandler):

    def __init__(self, rmr_xapp: RMRXapp, msgtype):
        super().__init__(rmr_xapp, msgtype)


    def request_handler(self, rmr_xapp, summary, sbuf):
        """
            Handles indication messages.

            Parameters
            ----------
            rmr_xapp: rmr Instance Context

            summary: dict (required)
                buffer content

            sbuf: str (required)
                length of the message
        """

        raw_data = summary[rmr.RMR_MS_PAYLOAD]
        meid = summary.get(rmr.RMR_MS_MEID, "")
        if isinstance(meid, bytes):
            meid = meid.decode("utf-8", errors="ignore").rstrip("\x00")
        self.logger.debug("IndicationHandler.request_handler:: Handler processing indication request")

        e2ap_pdu = E2AP_PDU_Descriptions.E2AP_PDU
        try:
            e2ap_pdu.from_aper(raw_data)    # raises ASN1ObjErr
            pdu = e2ap_pdu.get_val()
            self.logger.debug(f"E2AP Indication PDU is {pdu}")

            if pdu[0] == 'initiatingMessage':
                ies = e2ap_pdu.get_val_at(['initiatingMessage', 'value', 'RICindication', 'protocolIEs'])   # raises ASN1Err
                for ie in ies:
                    if ie['value'][0] == 'RICindicationHeader':
                        self.process_indication_header(ie['value'][1], meid)

                    elif ie['value'][0] == 'RICindicationMessage':
                        self.process_indication_message(ie['value'][1], meid)

            else:
                self.logger.error(f"Expecting PDU initiatingMessage, but got {pdu[0]}")

        except ASN1ObjErr as ex:
                self.logger.error(f"Unable to decode E2AP Indication. Reason: {type(ex).__name__} - {ex}")
        except ASN1Err as ex:
                self.logger.error(f"Unable to process E2AP Indication data. Reason: {type(ex).__name__} - {ex} in PDU {pdu}")

        finally:
            self._rmr_xapp.rmr_free(sbuf)

    def process_indication_header(self, header_bytes, meid=""):
        self.logger.debug(f"Processing RIC Indication Header from {meid}")
        header = E2SM_KPM_IEs.E2SM_KPM_IndicationHeader
        try:
            header.from_aper(header_bytes)  # raises ASN1ObjErr
            data = header.get_val_at(['indicationHeader-formats', 'indicationHeader-Format1'])  # raises ASN1Err
            self.logger.debug(f"KPM Indication Header from {meid} is {data}")

        except ASN1ObjErr as ex:
            self.logger.error(f"Unable to decode E2AP Indication Header. Reason: {type(ex).__name__} - {ex}")
        except ASN1Err as ex:
            self.logger.error(f"Unable to process KPM Indication Header. Reason: {type(ex).__name__} - {ex} in Header {header.get_val()}")

    def process_indication_message(self, message_bytes, meid=""):
        self.logger.debug(f"Processing RIC Indication Message from {meid}")
        message = E2SM_KPM_IEs.E2SM_KPM_IndicationMessage

        try:
            message.from_aper(message_bytes)  # raises ASN1ObjErr
            msg_val = message.get_val()

            self.logger.info("======================================================================")
            self.logger.info(f"[KPM-INDICATION] Telemetria recebida do Node: {meid}")
            self.logger.info("----------------------------------------------------------------------")

            fmt = msg_val[0] if isinstance(msg_val, tuple) else ""
            val = msg_val[1] if isinstance(msg_val, tuple) and len(msg_val) > 1 else msg_val

            if fmt == 'indicationMessage-formats' and isinstance(val, tuple):
                inner_fmt = val[0]
                inner_val = val[1]
                self.logger.info(f"  Formato da Mensagem: {inner_fmt}")

                meas_data = inner_val.get('measData', [])
                meas_info_list = inner_val.get('measInfoList', [])

                meas_names = []
                for item in meas_info_list:
                    m_type = item.get('measType', {})
                    if isinstance(m_type, tuple) and len(m_type) == 2:
                        meas_names.append(str(m_type[1]))
                    elif isinstance(m_type, dict) and 'measName' in m_type:
                        meas_names.append(str(m_type['measName']))
                    else:
                        meas_names.append("Metric")

                for data_item in meas_data:
                    records = data_item.get('measRecord', [])
                    for idx, rec in enumerate(records):
                        name = meas_names[idx] if idx < len(meas_names) else f"Metric_{idx+1}"
                        if isinstance(rec, tuple) and len(rec) == 2:
                            val_type, val_num = rec
                            self.logger.info(f"  - Métrica: {name:<28} -> {val_num} ({val_type})")
                        else:
                            self.logger.info(f"  - Métrica: {name:<28} -> {rec}")
            else:
                self.logger.info(f"  Conteúdo da Mensagem KPM: {msg_val}")

            self.logger.info("======================================================================")

        except ASN1ObjErr as ex:
            self.logger.error(f"Unable to decode E2AP Indication Message. Reason: {type(ex).__name__} - {ex}")
        except ASN1Err as ex:
            self.logger.error(f"Unable to process KPM Indication Message. Reason: {type(ex).__name__} - {ex} in Message {message.get_val()}")
