from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from elixir.domains.identity.workflows.activities import OTPDeliveryActivities, OTPDeliveryInput


@dataclass
class OTPWorkflowInput:
    user_id: str
    phone_e164: str
    otp_code: str
    otp_request_id: str


@workflow.defn
class OTPDeliveryWorkflow:
    @workflow.run
    async def run(self, input: OTPWorkflowInput) -> None:
        await workflow.execute_activity_method(
            OTPDeliveryActivities.send_otp_via_twilio,
            OTPDeliveryInput(
                phone_e164=input.phone_e164,
                otp_code=input.otp_code,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=2),
                backoff_coefficient=2.0,
            ),
        )
