"""""
Scheduler Module
APScheduler jobs for periodic inbox polling
"""

from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .gmail_service import GmailService, strip_quotes, build_mime
from .llm_service import LLMService
from .draft_repo import DraftRepository


class SchedulerService:
    def __init__(self) -> None:
        """Initialize the scheduler service with required components"""
        self.gmail = GmailService()
        self.llm = LLMService()
        self.db = DraftRepository()
        self.scheduler = BackgroundScheduler()

    def start(self) -> None:
        """Start the scheduler with configured jobs"""
        # Poll Gmail inbox every minute
        self.scheduler.add_job(
            self.poll_inbox,
            trigger=IntervalTrigger(minutes=1),
            id='poll_inbox',
            name='Poll Gmail inbox for new messages',
            replace_existing=True
        )
        self.scheduler.start()
        print(f"Scheduler started at {datetime.now()}")

    def shutdown(self) -> None:
        """Shutdown the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print(f"Scheduler shutdown at {datetime.now()}")

    def poll_inbox(self) -> None:
        """
        Poll the Gmail inbox for new unread messages,
        generate replies using the LLM, create drafts, and save them.
        """
        print(f"Polling inbox at {datetime.now()}")
        try:
            messages = self.gmail.list_unread()
            if not messages:
                print("No unread messages found")
                return
            print(f"Found {len(messages)} unread messages")

            for msg in messages:
                msg_id = msg.get('id')
                try:
                    full_message = self.gmail.get_message(msg_id)
                    clean_content = strip_quotes(full_message)
                    reply_text = self.llm.draft_reply(clean_content)

                    # Build MIME raw message with correct From address
                    thread_id = full_message.get('threadId') or msg_id
                    raw_mime = build_mime(reply_text, full_message, self.gmail.user_email)

                    # Create draft
                    draft = self.gmail.create_draft(raw_mime, thread_id)
                    draft_id = draft.get('id')

                    # Save to database
                    self.db.save_draft(msg_id, draft_id, reply_text, status="pending")

                    # Mark original message as read
                    self.gmail.mark_read(msg_id)

                    print(f"Processed message {msg_id}, created draft {draft_id}")

                except Exception as e:
                    print(f"Error processing message {msg_id}: {e}")
                    continue

        except Exception as e:
            print(f"Error in poll_inbox job: {e}")
