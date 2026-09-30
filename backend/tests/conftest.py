import os
import tempfile

# Must be set before claimtrace.db.session is imported.
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")
os.environ.setdefault("CLAIMTRACE_SEED", "1")
