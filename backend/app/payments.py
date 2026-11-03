# -*- coding: utf-8 -*-
"""支付网关抽象。

当前只走人工开通（管理员后台 + 兑换码），在线支付预留接口在这里：
以后接微信支付，只需实现 WeChatNativeProvider 并把 billing.payment_channel
改成 wechat，业务表（payment_orders）与开通逻辑都不用动。
"""
import os


class PaymentNotConfigured(Exception):
    """支付通道未配置（还没接商户号 / 没选通道）。"""


class PaymentProvider:
    name = "manual"

    def create_order(self, order):
        """为一条待支付订单生成支付凭据。

        order 是 models.PaymentOrder 对象。返回 {"pay_url": ..., "code_url": ...}
        """
        raise PaymentNotConfigured("在线支付尚未开放")

    def verify_notify(self, payload):
        """校验支付回调，返回标准化订单信息 dict；无效返回 None。"""
        return None


class ManualProvider(PaymentProvider):
    """人工开通：没有线上支付，只有后台操作和兑换码。"""
    name = "manual"

    def create_order(self, order):
        raise PaymentNotConfigured("在线支付即将开放，请联系管理员开通")


class WeChatNativeProvider(PaymentProvider):
    """微信支付 Native（扫码）。

    商户号、APIv3 密钥等必须放在环境变量里，不写进代码也不进仓库。
    没配齐就不启用，避免半配置状态下生成出付不了钱的二维码。
    """
    name = "wechat"

    def __init__(self):
        self.app_id = os.environ.get("WECHAT_MP_APP_ID", "").strip()
        self.mch_id = os.environ.get("WECHAT_MCH_ID", "").strip()
        self.api_v3_key = os.environ.get("WECHAT_API_V3_KEY", "").strip()
        self.notify_url = os.environ.get("WECHAT_NOTIFY_URL", "").strip()
        # 商户 API 密钥（v2）；v3 对账/退款用
        self.mch_secret = os.environ.get("WECHAT_MP_SECRET", "").strip()
        # 证书序列号与商户私钥路径（v3 签名用），按需配置
        self.serial_no = os.environ.get("WECHAT_SERIAL_NO", "").strip()
        self.private_key_path = os.environ.get("WECHAT_PRIVATE_KEY_PATH", "").strip()

    @property
    def configured(self):
        return bool(self.app_id and self.mch_id and self.api_v3_key)

    def create_order(self, order):
        if not self.configured:
            raise PaymentNotConfigured("微信支付未配置")
        raise NotImplementedError("微信支付下单待接入：补齐 requests 调用即可")


def get_provider(channel: str):
    """按 billing.payment_channel 返回对应的支付通道实现。"""
    channel = (channel or "manual").strip().lower()
    if channel == "wechat":
        provider = WeChatNativeProvider()
        return provider if provider.configured else ManualProvider()
    return ManualProvider()
