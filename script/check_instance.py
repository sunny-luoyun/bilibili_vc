#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.cvm.v20170312 import cvm_client, models

def load_credentials_from_json():
    """从同目录下的 credentials.json 读取密钥"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "credentials.json")
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"未找到密钥文件：{json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        cred_data = json.load(f)
    secret_id = cred_data.get("secret_id")
    secret_key = cred_data.get("secret_key")
    if not secret_id or not secret_key:
        raise ValueError("credentials.json 中必须包含 secret_id 和 secret_key")
    return secret_id, secret_key

def load_instance_ids_from_json(filename="instances_info.json"):
    """读取之前保存的实例信息，返回实例ID列表"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, filename)
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"未找到实例信息文件：{filepath}\n请先运行 startserver.py 创建实例。")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    instances = data.get("instances", [])
    instance_ids = [inst["InstanceId"] for inst in instances if "InstanceId" in inst]
    if not instance_ids:
        raise ValueError("实例信息文件中没有有效的实例ID。")
    return instance_ids, filepath

def delete_instances(client, instance_ids):
    """调用 TerminateInstances 接口删除指定实例（按量计费直接销毁）"""
    req = models.TerminateInstancesRequest()
    # 可选：释放关联的弹性IP（如有需要，取消下面一行的注释）
    # req.ReleaseAddress = True
    req.InstanceIds = instance_ids
    resp = client.TerminateInstances(req)
    return resp

def main():
    try:
        secret_id, secret_key = load_credentials_from_json()
        cred = credential.Credential(secret_id, secret_key)

        httpProfile = HttpProfile()
        httpProfile.endpoint = "cvm.ap-nanjing.tencentcloudapi.com"
        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile
        client = cvm_client.CvmClient(cred, "ap-nanjing", clientProfile)

        # 读取需要删除的实例ID
        instance_ids, json_file = load_instance_ids_from_json()
        print(f"准备删除以下实例：{instance_ids}")

        confirm = input("\n⚠️  删除操作不可逆，是否继续？(y/n): ").strip().lower()
        if confirm != 'y':
            print("操作已取消。")
            return

        # 执行删除
        resp = delete_instances(client, instance_ids)
        print(f"删除请求已发送，RequestId: {resp.RequestId}")

        # 删除成功后移除JSON文件（备份可选）
        backup = json_file + ".bak"
        if os.path.exists(json_file):
            os.rename(json_file, backup)
            print(f"实例信息文件已备份为：{backup}")

        print("实例删除流程已启动，通常几分钟后实例将被彻底销毁。")
        print("您可以通过腾讯云控制台确认实例状态。")

    except TencentCloudSDKException as err:
        print(f"腾讯云 API 错误：{err}")
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as err:
        print(f"错误：{err}")
    except Exception as err:
        print(f"未知错误：{err}")

if __name__ == "__main__":
    main()