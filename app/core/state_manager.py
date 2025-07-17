from contextlib import contextmanager
from app.core.logger import logging
from app.core.config import settings
from app.core.database import db
import subprocess

class StateManager:
    def __init__(self, wg_interface: str):
        self.wg_interface = wg_interface
        self.iptables_backup_text: str | None = None
        self.wg_config_backup_text: str | None = None

    def backup(self):

        # backup iptables
        result = subprocess.run(["iptables-save"], check=True, stdout=subprocess.PIPE, text=True)
        self.iptables_backup_text = result.stdout

        # backup WireGuard config
        result = subprocess.run(["wg", "showconf", self.wg_interface], check=True, stdout=subprocess.PIPE, text=True)
        self.wg_config_backup_text = result.stdout

        db.begin_transaction()
        logging.info("🔋  Backed up state in memory.")

    def restore(self):
        """
        Restores iptables and WireGuard config from in-memory backup.
        """

        try:
            if self.iptables_backup_text:
                subprocess.run(["iptables-restore"], input=self.iptables_backup_text, text=True, check=True)

            if self.wg_config_backup_text:
                subprocess.run(["wg", "setconf", self.wg_interface, "/dev/stdin"],
                               input=self.wg_config_backup_text, text=True, check=True)

            subprocess.run(["wg-quick", "down", self.wg_interface], check=False)
            subprocess.run(["wg-quick", "up", self.wg_interface], check=True)

            db.rollback_transaction()
            logging.info("🔄 System state restored.")
        except Exception as e:
            logging.error(f"❌  Failed to restore state: {e}")
            raise

    @contextmanager
    def saved_state(self):
        self.backup()
        try:
            yield
            db.commit_transaction()
            logging.info("✅  Transaction committed successfully.")
        except Exception as e:
            logging.warning(f"⛑️  Exception occurred: {e}. Restoring state...")
            self.restore()
            raise

    

state_manager = StateManager(wg_interface=settings.wg_interface)

