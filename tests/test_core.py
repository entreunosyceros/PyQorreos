import tempfile
import unittest
from pathlib import Path

from pyqorreos.core.classifier import MailCategory, MailClassifier
from pyqorreos.core.mail_cache import MailCache
from pyqorreos.core.mail_service import MailSummary, normalize_mail_datetime
from datetime import datetime, timezone


class ClassifierCacheTests(unittest.TestCase):
    def test_classifier_spam_keyword(self) -> None:
        clf = MailClassifier()
        cat = clf.classify(
            folder="INBOX",
            subject="Ganador de lotería",
            sender="spam@test.com",
            flagged=False,
            headers={},
        )
        self.assertEqual(cat, MailCategory.SPAM)

    def test_mail_cache_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            cache = MailCache(db)
            summary = MailSummary(
                uid="1",
                subject="Hola",
                sender="a@b.com",
                date=datetime(2024, 1, 1, 12, 0),
                seen=False,
                flagged=False,
                has_attachments=True,
                thread_key="thread-1",
            )
            cache.save_folder_ordered("acc", "INBOX", [summary])
            loaded = cache.load_folder("acc", "INBOX")
            self.assertEqual(len(loaded), 1)
            self.assertTrue(loaded[0].has_attachments)
            self.assertEqual(loaded[0].thread_key, "thread-1")

    def test_normalize_mail_datetime_sort(self) -> None:
        naive = datetime(2024, 1, 1)
        aware = datetime(2024, 6, 1, tzinfo=timezone.utc)
        summaries = [
            MailSummary("1", "a", "x", naive, False, False),
            MailSummary("2", "b", "y", aware, False, False),
        ]
        ordered = sorted(
            summaries,
            key=lambda s: normalize_mail_datetime(s.date) or datetime.min,
            reverse=True,
        )
        self.assertEqual(ordered[0].uid, "2")


if __name__ == "__main__":
    unittest.main()
