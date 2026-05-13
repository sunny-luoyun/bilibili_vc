#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import sys
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

def get_default_login_name(platform, os_name=""):
    """根据操作系统类型返回默认登录用户名"""
    platform_lower = platform.lower() if platform else ""
    os_lower = os_name.lower()
    if "windows" in platform_lower or "windows" in os_lower:
        return "Administrator"
    elif "ubuntu" in os_lower:
        return "ubuntu"
    else:
        return "root"

def wait_for_instances_running(client, instance_ids, timeout=300, interval=10):
    """
    轮询等待实例进入 RUNNING 状态并获取公网 IP
    返回列表，每个元素为 dict: {InstanceId, PublicIp, PrivateIp, OsName, Platform}
    """
    start_time = time.time()
    instance_info = []
    remaining_ids = set(instance_ids)

    while remaining_ids and (time.time() - start_time) < timeout:
        req = models.DescribeInstancesRequest()
        req.InstanceIds = list(remaining_ids)
        resp = client.DescribeInstances(req)

        for inst in resp.InstanceSet:
            if inst.InstanceState == "RUNNING" and inst.PublicIpAddresses and len(inst.PublicIpAddresses) > 0:
                info = {
                    "InstanceId": inst.InstanceId,
                    "PublicIp": inst.PublicIpAddresses[0],
                    "PrivateIp": inst.PrivateIpAddresses[0] if inst.PrivateIpAddresses else "",
                    "OsName": getattr(inst, "OsName", ""),
                    "Platform": getattr(inst, "Platform", ""),
                    "InstanceName": getattr(inst, "InstanceName", f"未命名-{inst.InstanceId}")
                }
                instance_info.append(info)
                remaining_ids.remove(inst.InstanceId)
                print(f"[{inst.InstanceId}] 已运行，公网IP: {info['PublicIp']}")
        if remaining_ids:
            time.sleep(interval)

    if remaining_ids:
        print(f"警告：以下实例未在 {timeout} 秒内获得公网IP或未运行：{remaining_ids}")
        # 对于未获得的，尝试再次查询当前状态，至少记录ID和已知信息
        if remaining_ids:
            req = models.DescribeInstancesRequest()
            req.InstanceIds = list(remaining_ids)
            resp = client.DescribeInstances(req)
            for inst in resp.InstanceSet:
                info = {
                    "InstanceId": inst.InstanceId,
                    "PublicIp": inst.PublicIpAddresses[0] if inst.PublicIpAddresses else "",
                    "PrivateIp": inst.PrivateIpAddresses[0] if inst.PrivateIpAddresses else "",
                    "OsName": getattr(inst, "OsName", ""),
                    "Platform": getattr(inst, "Platform", ""),
                    "InstanceName": getattr(inst, "InstanceName", f"未命名-{inst.InstanceId}")
                }
                instance_info.append(info)
    return instance_info

def save_instance_info(instance_list, filename="instances_info.json"):
    """保存实例信息到JSON文件"""
    output = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "instances": instance_list
    }
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)
    print(f"\n实例信息已保存至：{filepath}")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1, help="要创建的实例数量")
    args = parser.parse_args()
    instance_count = args.count
    try:
        secret_id, secret_key = load_credentials_from_json()
        cred = credential.Credential(secret_id, secret_key)

        # 配置（与原有 startserver.py 一致）
        httpProfile = HttpProfile()
        httpProfile.endpoint = "cvm.ap-nanjing.tencentcloudapi.com"
        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile
        client = cvm_client.CvmClient(cred, "ap-nanjing", clientProfile)

        # 构建创建请求参数（创建3个 Ubuntu 实例）
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
            "ImageId": "img-mmytdhbn",           # Ubuntu 镜像
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
            "InstanceCount": instance_count,                     # 创建实例
            "EnhancedService": {
                "SecurityService": {"Enabled": True},
                "MonitorService": {"Enabled": True},
                "AutomationService": {"Enabled": True}
            },
            "LoginSettings": {
                "Password": "X#7kPm$9qL@2wR&"     # 请确保密码符合安全规则（Ubuntu 同样支持密码登录）
            }
        }
        req.from_json_string(json.dumps(params))

        print("正在创建3个 Ubuntu CVM 实例，请稍候...")
        resp = client.RunInstances(req)
        result = json.loads(resp.to_json_string())
        instance_ids = result.get("InstanceIdSet", [])
        if not instance_ids:
            print("创建失败：未返回实例ID")
            return

        print(f"成功创建 {len(instance_ids)} 个实例，ID: {instance_ids}")
        print("等待实例启动并分配公网IP（最长等待5分钟）...")

        # 轮询获取实例运行状态及IP
        instance_info = wait_for_instances_running(client, instance_ids, timeout=300, interval=10)

        # 保存信息到JSON
        save_instance_info(instance_info)

        # 输出每个实例的登录信息
        print("\n" + "="*60)
        print("实例创建完成，详细信息如下：")
        for idx, info in enumerate(instance_info, 1):
            login_name = get_default_login_name(info.get("Platform", ""), info.get("OsName", ""))
            print(f"\n实例 {idx}: {info['InstanceId']}")
            print(f"  名称: {info['InstanceName']}")
            print(f"  操作系统: {info['OsName']}")
            print(f"  公网IP: {info['PublicIp']}")
            print(f"  内网IP: {info['PrivateIp']}")
            print(f"  登录用户: {login_name}")
            if info['PublicIp']:
                print(f"  SSH命令: ssh {login_name}@{info['PublicIp']}")
        print("="*60)

    except TencentCloudSDKException as err:
        print(f"腾讯云 API 错误：{err}")
    except Exception as err:
        print(f"错误：{err}")

if __name__ == "__main__":
    main()