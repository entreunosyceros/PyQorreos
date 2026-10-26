import unittest

from pyqorreos.core.email_html import block_remote_images_in_html
from pyqorreos.core.reply_utils import build_reply
from pyqorreos.core.mail_service import MailMessage
from datetime import datetime


class HtmlReplyTests(unittest.TestCase):
    def test_block_remote_images(self) -> None:
        html = '<img src="https://example.com/x.png">'
        blocked = block_remote_images_in_html(html)
        self.assertIn("data-blocked-src", blocked)
        self.assertIn('src="data:image/svg+xml', blocked)

    def test_restore_blocked_remote_images(self) -> None:
        from pyqorreos.core.email_html import restore_blocked_remote_images

        html = '<img src="https://example.com/x.png">'
        blocked = block_remote_images_in_html(html)
        restored = restore_blocked_remote_images(blocked)
        self.assertIn('src="https://example.com/x.png"', restored)

    def test_build_reply_includes_subject(self) -> None:
        msg = MailMessage(
            uid="1",
            subject="Prueba",
            sender="Bob <bob@test.com>",
            recipients="me@test.com",
            date=datetime(2024, 6, 1, 10, 0),
            body_text="Hola",
            body_html="<p>Hola</p>",
        )
        draft = build_reply(msg, "me@test.com")
        self.assertTrue(draft.subject.startswith("Re:"))
        self.assertIn("bob@test.com", draft.to)


if __name__ == "__main__":
    unittest.main()
