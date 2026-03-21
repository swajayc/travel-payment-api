from flask import Flask, request, jsonify
import stripe
import os
import json
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

PACKAGES = {
    "bali":     {"name": "Bali Escape",             "price": 99900},
    "paris":    {"name": "Paris Romantic Getaway",  "price": 129900},
    "kenya":    {"name": "Safari Adventure Kenya",  "price": 189900},
    "maldives": {"name": "Maldives Luxury Retreat", "price": 249900},
    "japan":    {"name": "Japan Explorer",          "price": 159900},
}

# ── Travel booking endpoint ──────────────────────────────────────────
@app.route("/get-payment-link", methods=["GET"])
def get_payment_link():
    package = request.args.get("package", "").lower()
    pkg = PACKAGES.get(package)

    if not pkg:
        return jsonify({"error": "Package not found"}), 404

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": pkg["name"]},
                "unit_amount": pkg["price"],
            },
            "quantity": 1,
        }],
        mode="payment",
        metadata={"package": package},
        success_url="https://yoursite.com/success",
        cancel_url="https://yoursite.com/cancel",
    )

    return jsonify({"url": session.url})


# ── Webhook handler ──────────────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    # ── Issuing: card authorization (approve/decline in real time) ──
    if event.type == "issuing_authorization.request":
        auth = event.data.object
        card_id = auth.card.id
        amount = auth.amount
        currency = auth.currency
        merchant = auth.merchant_data.name
        merchant_category = auth.merchant_data.category
        cost_centre = auth.card.metadata.get("cost_centre", "unknown")
        purpose = auth.card.metadata.get("purpose", "unknown")

        app.logger.info(f"AUTHORIZATION REQUEST RECEIVED")
        app.logger.info(f"Card: {card_id}")
        app.logger.info(f"Merchant: {merchant}")
        app.logger.info(f"Category: {merchant_category}")
        app.logger.info(f"Amount: {currency.upper()} {amount/100}")
        app.logger.info(f"Cost centre: {cost_centre}")
        app.logger.info(f"Purpose: {purpose}")

        # Rule 1: Block transactions over €200
        if amount > 20000:
            app.logger.info(f"DECLINED - amount EUR {amount/100} exceeds EUR 200 limit")
            stripe.issuing.Authorization.decline(auth.id)
            return jsonify({"approved": False})

        # Rule 2: Block certain merchant categories
        blocked_categories = ["gambling", "airlines", "lodging"]
        if merchant_category in blocked_categories:
            app.logger.info(f"DECLINED - category {merchant_category} is blocked")
            stripe.issuing.Authorization.decline(auth.id)
            return jsonify({"approved": False})

        # All checks passed
        app.logger.info(f"APPROVED")
        stripe.issuing.Authorization.approve(auth.id)
        return jsonify({"approved": True})

    # ── Issuing: transaction created after authorization ──
    elif event.type == "issuing_transaction.created":
        txn = event.data.object
        app.logger.info(f"TRANSACTION CREATED")
        app.logger.info(f"Card: {txn.card}")
        app.logger.info(f"Merchant: {txn.merchant_data.name}")
        app.logger.info(f"Amount: {abs(txn.amount)/100}")
        app.logger.info(f"Currency: {txn.currency.upper()}")
        # In production: write to database, update spend tracker,
        # notify finance team, sync to ERP

    # ── Checkout: travel booking payment ──
    elif event.type == "checkout.session.completed":
        session = event.data.object
        app.logger.info(f"TRAVEL PAYMENT SUCCESSFUL")
        app.logger.info(f"Package: {session.metadata.get('package')}")
        app.logger.info(f"Customer: {session.customer_details.email if session.customer_details else 'unknown'}")
        app.logger.info(f"Amount: EUR {session.amount_total/100}")

    elif event.type == "checkout.session.expired":
        session = event.data.object
        app.logger.info(f"CHECKOUT ABANDONED")
        app.logger.info(f"Package: {session.metadata.get('package')}")

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
