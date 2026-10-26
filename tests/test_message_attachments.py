import email
import unittest

from pyqorreos.core.message_attachments import (
    extract_attachments,
    has_attachments_heuristic,
)


class MessageAttachmentTests(unittest.TestCase):
    def test_has_attachments_heuristic(self) -> None:
        self.assertTrue(has_attachments_heuristic("multipart/mixed; boundary=x"))
        self.assertFalse(has_attachments_heuristic("text/plain"))

    def test_extract_attachments(self) -> None:
        raw = (
            "From: a@b.com\nTo: c@d.com\nSubject: test\n"
            "MIME-Version: 1.0\nContent-Type: multipart/mixed; boundary=abc\n\n"
            "--abc\nContent-Type: text/plain\n\nHola\n"
            "--abc\nContent-Type: application/pdf\n"
            'Content-Disposition: attachment; filename="doc.pdf"\n\n'
            "%PDF-1.4\n"
            "--abc--\n"
        )
        msg = email.message_from_string(raw)
        attachments = extract_attachments(msg)
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].filename, "doc.pdf")


if __name__ == "__main__":
    unittest.main()
