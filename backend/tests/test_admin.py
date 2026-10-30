"""Unit tests for administrative schemas and validation constraints."""
import pytest
from pydantic import ValidationError

from app.models.enums import AccountStatus
from app.schemas.admin import (
    GarageModerationRequest,
    ProfileChangeDecisionRequest,
    RegistrationDecisionRequest,
    ReviewReportDecisionRequest,
    UserStatusUpdateRequest,
)


def test_registration_decision_validation():
    # Valid approve
    a1 = RegistrationDecisionRequest(decision="APPROVE", expected_version=1)
    assert a1.decision == "APPROVE"
    assert a1.rejection_reason is None

    # Valid reject with reason
    r1 = RegistrationDecisionRequest(
        decision="REJECT",
        expected_version=1,
        rejection_reason="Invalid address documentation.",
    )
    assert r1.decision == "REJECT"
    assert r1.rejection_reason == "Invalid address documentation."

    # Reject without reason must fail
    with pytest.raises(ValidationError):
        RegistrationDecisionRequest(decision="REJECT", expected_version=1)

    with pytest.raises(ValidationError):
        RegistrationDecisionRequest(decision="REJECT", expected_version=1, rejection_reason="   ")


def test_profile_change_decision_validation():
    # Approve
    a1 = ProfileChangeDecisionRequest(decision="APPROVE")
    assert a1.decision == "APPROVE"

    # Reject with reason
    r1 = ProfileChangeDecisionRequest(decision="REJECT", rejection_reason="Cannot verify new coordinates.")
    assert r1.rejection_reason == "Cannot verify new coordinates."

    # Reject without reason must fail
    with pytest.raises(ValidationError):
        ProfileChangeDecisionRequest(decision="REJECT")


def test_garage_moderation_validation():
    # Suspend requires reason
    with pytest.raises(ValidationError):
        GarageModerationRequest(action="SUSPEND")

    s1 = GarageModerationRequest(action="SUSPEND", reason="Multiple spam complaints.")
    assert s1.reason == "Multiple spam complaints."

    # Restore does not require reason
    r1 = GarageModerationRequest(action="RESTORE")
    assert r1.action == "RESTORE"


def test_user_status_update_validation():
    # Suspend requires reason
    with pytest.raises(ValidationError):
        UserStatusUpdateRequest(status=AccountStatus.SUSPENDED)

    s1 = UserStatusUpdateRequest(status=AccountStatus.SUSPENDED, reason="Suspected fraudulent activity.")
    assert s1.reason == "Suspected fraudulent activity."

    # Active does not require reason
    a1 = UserStatusUpdateRequest(status=AccountStatus.ACTIVE)
    assert a1.status == AccountStatus.ACTIVE


def test_review_report_decision_validation():
    # Mandatory note
    d1 = ReviewReportDecisionRequest(decision="REMOVE_REVIEW", note="Confirmed hate speech violation.")
    assert d1.note == "Confirmed hate speech violation."

    with pytest.raises(ValidationError):
        ReviewReportDecisionRequest(decision="REMOVE_REVIEW", note="  ")

