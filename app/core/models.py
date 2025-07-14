from contextlib import contextmanager
from pydantic import BaseModel
from app.core.config import settings
import tempfile, os, subprocess, shutil, logging

class Peer(BaseModel):
    username: str
    public_key: str
    preshared_key: str
    address: str

class Service(Peer):
    name: str
    department: str

class Subnet(BaseModel):
    subnet: str
    name: str
    description: str

class StateManager:
    def __init__(self, wg_interface: str):
        self.wg_interface = wg_interface
        self.backup_dir = tempfile.mkdtemp(prefix="driftcove_backup_")
        self._iptables_backup_path = os.path.join(self.backup_dir, "iptables.rules")
        self._wg_backup_path = os.path.join(self.backup_dir, f"{wg_interface}.conf.bak")

    def backup(self):

        from app.core.database import db
        # Backup iptables rules
        with open(self._iptables_backup_path, "w") as f:
            subprocess.run(["iptables-save"], stdout=f, check=True)

        # Backup WireGuard config
        wg_conf = f"/etc/wireguard/{self.wg_interface}.conf"
        shutil.copy(wg_conf, self._wg_backup_path)

        logging.info(f"Backed up state to {self.backup_dir}")
        logging.info("Initiating database transaction")
        db.begin_transaction()

    def restore(self):

        """
        Restores the system state from the backup.
        """
        from app.core.database import db
        try:
            subprocess.run(["iptables-restore"], stdin=open(self._iptables_backup_path), check=True)
            shutil.copy(self._wg_backup_path, f"/etc/wireguard/{self.wg_interface}.conf")
            subprocess.run(["wg-quick", "down", self.wg_interface], check=False)
            subprocess.run(["wg-quick", "up", self.wg_interface], check=True)
            db.rollback_transaction()
            logging.warning("System state restored.")
        except Exception as e:
            logging.error(f"Failed to restore state: {e}")
            raise

    @contextmanager
    def saved_state(self):
        """
        Saved state backs up all the configuration files and starts a transaction on the database.
        """
        from app.core.database import db
        self.backup()
        try:
            yield
            db.commit_transaction()
            logging.info("Transaction committed successfully.")
        except Exception as e:
            logging.error(f"Exception occurred: {e}. Restoring state...")
            self.restore()
            raise

    

state_manager = StateManager(wg_interface=settings.wg_interface)