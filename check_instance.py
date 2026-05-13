# -*- coding: utf-8 -*-

import os
import json
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

def get_instance_info(client, instance_id):
    """查询单个实例的详细信息"""
    req = models.DescribeInstancesRequest()
    req.InstanceIds = [instance_id]
    resp = client.DescribeInstances(req)
    if not resp.InstanceSet:
        raise ValueError(f"未找到实例 ID: {instance_id}")
    return resp.InstanceSet[0]

def get_default_login_name(platform, os_name=""):
    """根据操作系统类型返回默认登录用户名"""
    platform_lower = platform.lower() if platform else ""
    os_lower = os_name.lower()
    if "windows" in platform_lower or "windows" in os_lower:
        return "Administrator"
    elif "ubuntu" in os_lower:
        return "ubuntu"
    else:
        return "root"  # CentOS, Debian, TencentOS 等

def main(instance_id):
    try:
        secret_id, secret_key = load_credentials_from_json()
        cred = credential.Credential(secret_id, secret_key)

        # 配置（与创建脚本保持一致）
        httpProfile = HttpProfile()
        httpProfile.endpoint = "cvm.ap-nanjing.tencentcloudapi.com"
        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile
        client = cvm_client.CvmClient(cred, "ap-nanjing", clientProfile)

        # 查询实例详情
        instance = get_instance_info(client, instance_id)

        # 提取关键信息
        state = instance.InstanceState          # PENDING, RUNNING, STOPPED 等
        public_ips = instance.PublicIpAddresses if instance.PublicIpAddresses else []
        private_ips = instance.PrivateIpAddresses if instance.PrivateIpAddresses else []
        platform = getattr(instance, 'Platform', 'Unknown')
        os_name = getattr(instance, 'OsName', '')
        login_name = get_default_login_name(platform, os_name)

        print("\n" + "="*50)
        print(f"实例 ID      : {instance_id}")
        print(f"实例名称     : {getattr(instance, 'InstanceName', '未命名')}")
        print(f"状态         : {state}")
        print(f"系统平台     : {platform}   ({os_name})")
        print(f"默认登录账号 : {login_name}")
        print(f"公网 IP      : {public_ips[0] if public_ips else '无公网IP'}")
        print(f"内网 IP      : {private_ips[0] if private_ips else '无内网IP'}")
        print("="*50)

        # 登录提示
        if state == "RUNNING" and public_ips:
            print(f"\n✅ 实例已运行 🔗 公网IP: {public_ips[0]}")
            print(f"👉 SSH 登录命令（Linux）： ssh {login_name}@{public_ips[0]}")
            print(f"   如果使用密码登录，请先通过控制台或 API 重置密码。")
            print(f"   （重置密码可能会强制关机，请注意服务影响）")
        elif state == "RUNNING" and not public_ips:
            print("\n⚠️ 实例运行中，但没有分配公网IP，无法从外网直接登录。")
            print("   可以绑定弹性公网IP或通过跳板机内网访问。")
        elif state == "STOPPED":
            print("\n⏸️ 实例已关机，请先启动实例再登录。")
        else:
            print(f"\n⏳ 实例状态为 {state}，请等待变为 RUNNING 后再尝试登录。")

        # 如果是 Windows 实例，提示获取密码的方法
        if "windows" in platform.lower() or "windows" in os_name.lower():
            print("\n💡 Windows 实例初始密码为加密状态，需使用私钥解密。")
            print("   控制台操作：实例列表 -> 更多 -> 密码/密钥 -> 获取管理员密码")

    except TencentCloudSDKException as err:
        print(f"腾讯云 API 错误：{err}")
    except Exception as err:
        print(f"错误：{err}")

if __name__ == "__main__":
    # 默认使用上次创建的实例 ID，也可以从命令行参数获取
    default_instance_id = "ins-5b0nyfpg"
    instance_id = sys.argv[1] if len(sys.argv) > 1 else default_instance_id
    main(instance_id)