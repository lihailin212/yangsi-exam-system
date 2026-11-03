# -*- coding: utf-8 -*-
"""短信验证码通道抽象。

目前只有「预留接口」：没配置短信服务商时相关接口一律返回 501，
前端会隐藏短信登录入口。配置阿里云/腾讯云后实现 send_sms_code 即可启用。
"""
import os
import random


class SmsNotConfigured(Exception):
    """短信通道未配置。"""


def sms_configured() -> bool:
    return bool(
        os.environ.get("ALIYUN_SMS_ACCESS_KEY_ID", "").strip()
        and os.environ.get("ALIYUN_SMS_ACCESS_KEY_SECRET", "").strip()
        and os.environ.get("ALIYUN_SMS_TEMPLATE_CODE", "").strip()
    )


def sign_name() -> str:
    """短信签名（阿里云要求带签名发送）。没配也不影响验证码流程，只是发不出去。"""
    return os.environ.get("ALIYUN_SMS_SIGN_NAME", "").strip()


def generate_code(length: int = 6) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def send_sms_code(phone: str, code: str) -> None:
    """把验证码发给用户。没配置通道时抛 SmsNotConfigured。"""
    if not sms_configured():
        raise SmsNotConfigured("短信服务未配置")
    raise NotImplementedError("短信发送待接入：补齐阿里云/腾讯云调用即可")
