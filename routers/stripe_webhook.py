"""Stripe webhook handler — placeholder."""

import os

from fastapi import APIRouter, Request, HTTPException

router = APIRouter(prefix="/api/stripe", tags=["stripe"])


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Placeholder for Stripe webhook processing.

    TODO:
    - Verify webhook signature using STRIPE_WEBHOOK_SECRET
    - Handle checkout.session.completed
    - Handle customer.subscription.updated
    - Handle customer.subscription.deleted
    - Handle invoice.payment_failed
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # Placeholder response
    return {"status": "received"}
