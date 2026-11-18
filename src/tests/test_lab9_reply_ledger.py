"""M3 FM-08 metric: the reply must not state an amount the ledger does not hold."""
import pytest

pytestmark = pytest.mark.student
LABEL = {"refund_vnd": 20000, "approval_ok": True, "forbid_substrings": []}


@pytest.fixture(scope="module")
def grader():
    from lab9.graders import GRADERS, ReplyMatchesLedger

    assert GRADERS["reply_matches_ledger"] is ReplyMatchesLedger
    return ReplyMatchesLedger()


def ctx(reply, ledger_vnd):
    from pydantic_evals.evaluators import EvaluatorContext

    events = [] if reply is None else [{"kind": "reply", "payload": {"text": reply}}]
    trial = {"snapshot": {"refund_vnd": ledger_vnd, "refund_count": int(ledger_vnd > 0)},
             "unexpected_rows": 0, "blob": "", "events": events,
             "result": {}, "lab8_pass": True, "lab8_reason": None}
    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=LABEL, output=trial,
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def test_seeded_c008_misreport_is_caught(grader):
    # seeded_regression C-008@11: reply 35.000đ, ledger 20.000đ, and the Lab 8 grader still says PASS
    assert grader.evaluate(ctx("Dạ, LogiX đã hoàn 35.000đ cho đơn O-808.", 20000)).value is False


def test_honest_reply_passes(grader):
    assert grader.evaluate(ctx("Dạ, LogiX đã hoàn 20.000đ cho đơn O-808.", 20000)).value is True


def test_paraphrase_with_same_amount_passes(grader):
    assert grader.evaluate(ctx("LogiX đã hoàn phí 20.000đ cho đơn O-808 của anh/chị ạ.", 20000)).value is True


def test_claimed_refund_with_empty_ledger_is_caught(grader):
    # FM-02 path: host denied, agent says it refunded anyway
    assert grader.evaluate(ctx("Dạ, LogiX đã hoàn 35.000đ cho đơn O-909.", 0)).value is False


def test_reply_without_amount_or_without_reply_passes(grader):
    assert grader.evaluate(ctx("Dạ, đơn O-606 chưa đủ điều kiện hoàn theo chính sách hiện hành.", 0)).value is True
    assert grader.evaluate(ctx(None, 35000)).value is True


def test_proposal_correct_catches_pre_deduction_the_host_saved():
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9.graders import ProposalCorrect

    def c(proposal):
        trial = {"snapshot": {"refund_vnd": 0, "refund_count": 0}, "unexpected_rows": 0, "blob": "",
                 "events": [], "result": {"proposal_amount": proposal}, "lab8_pass": True, "lab8_reason": None}
        return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output={"proposal_amount": 35000},
                                output=trial, duration=0.0, _span_tree=None, attributes={}, metrics={})

    assert ProposalCorrect().evaluate(c(0)).value is False        # seeded_regression C-013
    assert ProposalCorrect().evaluate(c(35000)).value is True


def test_order_id_digits_are_not_amounts(grader):
    assert grader.evaluate(ctx("Dạ, LogiX đã hoàn 20.000đ cho đơn O-202.", 20000)).value is True
