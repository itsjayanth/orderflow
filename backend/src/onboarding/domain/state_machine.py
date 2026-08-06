from identity.domain.models import ONBOARDING_STATUSES, Merchant

OnboardingStatus = str

# ARCHITECTURE.md Section 5: strictly linear, no step-skipping. Built as a
# frozenset of adjacent pairs from ONBOARDING_STATUSES (the single source of
# truth for the six values, defined alongside Merchant since it owns the
# column) rather than duplicating the ordering here.
ONBOARDING_TRANSITIONS: frozenset[tuple[OnboardingStatus, OnboardingStatus]] = frozenset(
    zip(ONBOARDING_STATUSES, ONBOARDING_STATUSES[1:], strict=False)
)


class IllegalOnboardingTransitionError(Exception):
    def __init__(self, from_status: str, to_status: str) -> None:
        super().__init__(f"illegal onboarding transition: {from_status!r} -> {to_status!r}")
        self.from_status = from_status
        self.to_status = to_status


def transition_onboarding_status(merchant: Merchant, to_status: OnboardingStatus) -> Merchant:
    """Validates and applies a single forward step per Section 5. Callers are
    expected to check `merchant.onboarding_status` first and only call this
    when it's exactly the expected prior step -- this raises rather than
    silently no-opping so a real logic error (e.g. accidentally requesting a
    skip) surfaces immediately, same as orders/domain/state_machine.py."""
    from_status = merchant.onboarding_status
    if (from_status, to_status) not in ONBOARDING_TRANSITIONS:
        raise IllegalOnboardingTransitionError(from_status, to_status)
    merchant.onboarding_status = to_status
    return merchant
