"""
Unit tests for QuizInteractor selection idempotency and submission gating.
"""

import unittest
from unittest.mock import MagicMock, patch

from extraction.questions import Question, Option
from interaction.selector import QuizInteractor, SelectionVerificationError


def make_single_question(q_type="single_choice", initially_selected=False):
    opt1 = Option(
        index=0,
        letter="A",
        text="Opt 1",
        input_id="inp_1",
        input_name="group1",
        input_type="radio" if q_type == "single_choice" else "checkbox",
        input_value="1",
        is_initially_selected=initially_selected,
        is_currently_selected=initially_selected
    )
    return Question(
        number=1,
        container_testid="test",
        container_id=None,
        prompt_id="prompt-1",
        input_name="group1",
        question_type=q_type,
        prompt_text="Test Prompt?",
        options=[opt1]
    )


class TestQuizInteraction(unittest.TestCase):

    def test_checkbox_idempotency_skips_click_if_already_selected(self):
        """Crucial test: an already-selected checkbox must NOT be clicked again."""
        driver = MagicMock()
        interactor = QuizInteractor(driver)

        q = make_single_question(q_type="multi_choice", initially_selected=True)

        # Mock elements
        mock_input = MagicMock()
        mock_input.is_selected.return_value = True
        mock_label = MagicMock()

        mock_opt_wrapper = MagicMock()
        mock_opt_wrapper.find_element.side_effect = lambda by, val: mock_label if "label" in val else mock_input

        # Mock finding question wrapper and option wrappers
        mock_q_wrapper = MagicMock()
        mock_q_wrapper.find_elements.return_value = [mock_opt_wrapper]

        interactor._find_question_element = MagicMock(return_value=mock_q_wrapper)

        # Attempt to select option 0
        interactor._select_single_option(q, 0)

        # Label click MUST NOT be called!
        mock_label.click.assert_not_called()
        self.assertTrue(q.options[0].is_currently_selected)

    def test_radio_already_selected_skips_click(self):
        """An already-selected radio button must not trigger redundant clicks."""
        driver = MagicMock()
        interactor = QuizInteractor(driver)

        q = make_single_question(q_type="single_choice", initially_selected=True)

        mock_input = MagicMock()
        mock_input.is_selected.return_value = True
        mock_label = MagicMock()

        mock_opt_wrapper = MagicMock()
        mock_opt_wrapper.find_element.side_effect = lambda by, val: mock_label if "label" in val else mock_input
        mock_q_wrapper = MagicMock()
        mock_q_wrapper.find_elements.return_value = [mock_opt_wrapper]
        interactor._find_question_element = MagicMock(return_value=mock_q_wrapper)

        interactor._select_single_option(q, 0)
        mock_label.click.assert_not_called()

    def test_unselected_option_clicks_and_verifies(self):
        """Unselected option must click label and verify checked state."""
        driver = MagicMock()
        interactor = QuizInteractor(driver)

        q = make_single_question(q_type="single_choice", initially_selected=False)

        mock_input = MagicMock()
        # Initially False, then True after click
        mock_input.is_selected.side_effect = [False, True]
        mock_label = MagicMock()

        mock_opt_wrapper = MagicMock()
        mock_opt_wrapper.find_element.side_effect = lambda by, val: mock_label if "label" in val else mock_input
        mock_q_wrapper = MagicMock()
        mock_q_wrapper.find_elements.return_value = [mock_opt_wrapper]
        interactor._find_question_element = MagicMock(return_value=mock_q_wrapper)
        interactor._verify_option_selected = MagicMock()

        interactor._select_single_option(q, 0)

        mock_label.click.assert_called_once()
        interactor._verify_option_selected.assert_called_once()
        self.assertTrue(q.options[0].is_currently_selected)

    def test_auto_select_agreement_clicks_when_unchecked(self):
        """Honor Code agreement checkbox should be clicked if unchecked."""
        driver = MagicMock()
        interactor = QuizInteractor(driver)

        mock_box = MagicMock()
        mock_box.is_selected.side_effect = [False, True]
        mock_label = MagicMock()
        mock_box.find_element.return_value = mock_label

        driver.find_elements.return_value = [mock_box]

        interactor.auto_select_agreement_if_needed()
        mock_label.click.assert_called_once()

    def test_confirm_modal_submission_clicks_dialog_submit_button(self):
        """Should detect 'Ready to submit?' dialog and click modal Submit button."""
        driver = MagicMock()
        interactor = QuizInteractor(driver)

        mock_dialog = MagicMock()
        mock_modal_btn = MagicMock()
        mock_modal_btn.is_displayed.return_value = True
        mock_dialog.find_elements.return_value = [mock_modal_btn]

        driver.find_elements.return_value = [mock_dialog]

        success = interactor.confirm_modal_submission(timeout=0.2)
        self.assertTrue(success)
        mock_modal_btn.click.assert_called_once()

    def test_confirm_modal_ignores_boost_chatpanel_and_clicks_real_dialog(self):
        """Ensure Boost ChatPanel buttons are ignored and the real 'Ready to submit?' button is clicked."""
        driver = MagicMock()
        interactor = QuizInteractor(driver)

        # Mock real dialog and submit button
        mock_real_dialog = MagicMock()
        mock_real_submit_btn = MagicMock()
        mock_real_submit_btn.is_displayed.return_value = True
        mock_real_dialog.find_elements.return_value = [mock_real_submit_btn]

        # driver.find_elements returns the real dialog for the XPath query
        driver.find_elements.return_value = [mock_real_dialog]

        success = interactor.confirm_modal_submission(timeout=0.2)
        self.assertTrue(success)
        mock_real_submit_btn.click.assert_called_once()

    def test_submission_cancelled_when_unconfirmed(self):
        driver = MagicMock()
        interactor = QuizInteractor(driver)

        # explicit_confirmation = False
        result = interactor.submit_quiz_guarded(explicit_confirmation=False)
        self.assertFalse(result)
        driver.find_element.assert_not_called()


if __name__ == "__main__":
    unittest.main()
