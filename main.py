from flask import Flask, request, jsonify
import stripe
import os

app = Flask(__name__)

# Stripe secret key loaded from environment variable (secure way)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

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
        success_url="https://yoursite.com/success",
        cancel_url="https://yoursite.com/cancel",
    )

    return jsonify({"url": session.url})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
```

