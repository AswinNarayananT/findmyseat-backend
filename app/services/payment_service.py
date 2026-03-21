import razorpay
from app.core.config import settings


razorpay_client = razorpay.Client(
    auth=(
        settings.RAZORPAY_KEY_ID,
        settings.RAZORPAY_KEY_SECRET
    )
)


class PaymentService:

    @staticmethod
    def create_order(amount: int, currency: str = "INR", receipt: str | None = None):
        data = {
            "amount": amount,
            "currency": currency,
            "receipt": receipt,
            "payment_capture": 1
        }

        order = razorpay_client.order.create(data)

        return order


    @staticmethod
    def verify_payment(
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
    ):
        params = {
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature
        }

        try:
            razorpay_client.utility.verify_payment_signature(params)
            return True

        except razorpay.errors.SignatureVerificationError:
            return False