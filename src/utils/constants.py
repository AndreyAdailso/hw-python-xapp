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

class Constants:
    A1_POLICY_QUERY = 20012
    HELLOWORLD_POLICY_ID = 2
    RIC_HEALTH_CHECK_REQ = 100
    RIC_HEALTH_CHECK_RESP = 101
    A1_POLICY_REQ = 20010
    A1_POLICY_RESP = 20011
    RIC_ALARM_UPDATE = 110
    ACTION_TYPE = "report"
    SUBSCRIPTION_PATH = "http://service-{}-{}-http.{}:{}{}"
    PLT_NAMESPACE = "ricplt"
    SUBSCRIPTION_SERVICE = "submgr"
    SUBSCRIPTION_PORT = "8088"
    SUBSCRIPTION_RESOURCE = "/ric/v1/subscriptions"
    SUBSCRIPTION_REQ = 12011
    RIC_INDICATION = 12050
    RIC_CONTROL_REQ = 12040
    RIC_CONTROL_ACK = 12041
    RIC_CONTROL_FAILURE = 12042

    KPM_RAN_FUNCTION_ID = 200
    RC_RAN_FUNCTION_ID = 300

    # E2SM-RC v03.00 section 7.6.3: CONTROL Service Style 2 (Radio Resource Allocation Control),
    # Control Action 6 (Slice-level PRB quota)
    RC_STYLE_TYPE_RADIO_RESOURCE_ALLOCATION = 2
    RC_ACTION_ID_SLICE_PRB_QUOTA = 6
    # E2SM-RC v03.00 section 8.4.3.6: RAN Parameter IDs for Slice-level PRB quota
    RC_PARAM_RRM_POLICY_RATIO_LIST = 1
    RC_PARAM_RRM_POLICY_RATIO_GROUP = 2
    RC_PARAM_RRM_POLICY = 3
    RC_PARAM_RRM_POLICY_MEMBER_LIST = 5
    RC_PARAM_RRM_POLICY_MEMBER = 6
    RC_PARAM_PLMN_IDENTITY = 7
    RC_PARAM_S_NSSAI = 8
    RC_PARAM_SST = 9
    RC_PARAM_SD = 10
    RC_PARAM_MIN_PRB_RATIO = 11
    RC_PARAM_MAX_PRB_RATIO = 12
    RC_PARAM_DEDICATED_PRB_RATIO = 13
    # PLMN Identity (3 octets, TS 38.473) sent in each RRM Policy Member; None = omitted
    RC_PLMN_IDENTITY = None

    DEFAULT_HTTP_PORT = 8080
    DEFAULT_RMRROUTE_PORT = 4561
    DEFAULT_RMRDATA_PORT = 4560
