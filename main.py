from flask import Flask, request, jsonify
import stripe
import os
import json

app = Flask(__name__)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

PACKAGES = {
    "bali":     {"name": "Bali Escape",             "price": 99900},
    "paris":    {"name": "Paris Romantic Getaway",  "price": 129900},
    "kenya":    {"name": "Safari Adventure Kenya",  "price": 189900},
    "maldives": {"name": "Maldives Luxury Retreat", "price": 249900},
    "japan":    {"name": "Japan Explorer",          "price": 159900},
}

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
        # Pass the package name into the session so webhook knows what was booked
        metadata={"package": package},
        success_url="https://yoursite.com/success",
        cancel_url="https://yoursite.com/cancel",
    )

    return jsonify({"url": session.url})


@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")

    # Verify the request actually came from Stripe (security check)
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        # Invalid payload
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        # Invalid signature — request didn't come from Stripe
        return jsonify({"error": "Invalid signature"}), 400

    # Handle successful payment
    if event.type == "checkout.session.completed":
        session = event.data.object
        package = session.metadata.get("package")
        customer_email = session.customer_details.email if session.customer_details else "unknown"
        amount = session.amount_total / 100  # Convert cents back to euros

        print(f"✅ Payment successful!")
        print(f"   Package: {package}")
        print(f"   Customer: {customer_email}")
        print(f"   Amount: €{amount}")
        # In production: trigger email, create Zendesk ticket, update CRM etc.

    # Handle abandoned/expired checkout
    elif event.type == "checkout.session.expired":
        session = event.data.object
        package = session.metadata.get("package")
        print(f"❌ Checkout abandoned for package: {package}")
        # In production: follow up email, create Zendesk ticket for sales team etc.

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
