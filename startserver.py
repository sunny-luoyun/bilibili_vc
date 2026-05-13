# -*- coding: utf-8 -*-

import os
import json
import types
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.cvm.v20170312 import cvm_client, models


def load_credentials_from_json():
    """从同目录下的 credentials.json 文件中读取 SecretId 和 SecretKey"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "credentials.json")

    if not os.path.exists(json_path):
        raise FileNotFoundError(
            f"未找到密钥文件：{json_path}\n"
            "请在该目录下创建 credentials.json 文件，格式如下：\n"
            '{\n    "secret_id": "你的SecretId",\n    "secret_key": "你的SecretKey"\n}'
        )

    with open(json_path, "r", encoding="utf-8") as f:
        cred_data = json.load(f)

    secret_id = cred_data.get("secret_id")
    secret_key = cred_data.get("secret_key")

    if not secret_id or not secret_key:
        raise ValueError("credentials.json 中必须包含 secret_id 和 secret_key 字段")

    return secret_id, secret_key


try:
    # 1. 从 JSON 文件加载密钥
    secret_id, secret_key = load_credentials_from_json()

    # 2. 创建凭证对象
    cred = credential.Credential(secret_id, secret_key)

    # 3. 配置 http 选项（可选的）
    httpProfile = HttpProfile()
    httpProfile.endpoint = "cvm.ap-nanjing.tencentcloudapi.com"

    # 4. 实例化 client 选项
    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile

    # 5. 创建 CVM 客户端
    client = cvm_client.CvmClient(cred, "ap-nanjing", clientProfile)

    # 6. 创建请求对象并填充参数
    req = models.RunInstancesRequest()
    params = {
        "InstanceChargeType": "POSTPAID_BY_HOUR",
        "DisableApiTermination": False,
        "Placement": {
            "Zone": "ap-nanjing-1",
            "ProjectId": 0
        },
        "VirtualPrivateCloud": {
            "AsVpcGateway": False,
            "VpcId": "vpc-itz0pg3d",
            "SubnetId": "subnet-oav59or2",
            "Ipv6AddressCount": 0
        },
        "InstanceType": "SA9.MEDIUM2",
        "ImageId": "img-6jb5wacd",
        "SystemDisk": {
            "DiskSize": 50,
            "DiskType": "CLOUD_BSSD"
        },
        "InternetAccessible": {
            "InternetMaxBandwidthOut": 20,
            "PublicIpAssigned": True,
            "InternetChargeType": "TRAFFIC_POSTPAID_BY_HOUR",
            "InternetServiceProvider": "BGP"
        },
        "SecurityGroupIds": ["sg-pt0cvy96"],
        "InstanceCount": 1,
        "EnhancedService": {
            "SecurityService": {
                "Enabled": True
            },
            "MonitorService": {
                "Enabled": True
            },
            "AutomationService": {
                "Enabled": True
            }
        },
        "LoginSettings": {  # 添加登录设置
            "Password": "Sunny1318860595."  # 设置你的密码，请修改为符合规则的安全密码
        }
    }
    req.from_json_string(json.dumps(params))

    # 7. 发起请求并打印结果
    resp = client.RunInstances(req)
    print(resp.to_json_string())

except TencentCloudSDKException as err:
    print(f"腾讯云 SDK 错误：{err}")
except (FileNotFoundError, ValueError, json.JSONDecodeError) as err:
    print(f"读取密钥文件失败：{err}")