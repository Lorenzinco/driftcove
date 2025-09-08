from contextlib import contextmanager
from backend.core.logger import logging
from backend.core.config import settings
from backend.core.database import db
from backend.core.nftables import restore_dcv_table, backup_dcv_table
import subprocess

class StateManager:
    def __init__(self, wg_interface: str):
        self.wg_interface = wg_interface
        self.dcv_backup_text: str | None = None
        self.wg_config_backup_text: str | None = None

    def backup(self):

        # backup nftables dcv table
        self.dcv_backup_text = backup_dcv_table()

        # backup WireGuard config
        result = subprocess.run(["wg", "showconf", self.wg_interface], check=True, stdout=subprocess.PIPE, text=True)
        self.wg_config_backup_text = result.stdout

        db.begin_transaction()
        logging.info("🔋  Backed up state in memory.")

    def restore(self):
        """
        Restores nftables dcv table and WireGuard config from in-memory backup.
        """

        try:
            if self.dcv_backup_text:
                restore_dcv_table(self.dcv_backup_text)

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

